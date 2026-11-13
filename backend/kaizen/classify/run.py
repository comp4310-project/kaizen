"""Labels every saved comment that has no labels yet (FR3).

Comments that already have labels are skipped, so rerunning after a failure only pays for
the comments that were missed. Batches go out in parallel; all database writes happen in
the calling thread.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Protocol, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from kaizen.classify.claude import LabelError
from kaizen.classify.labels import Labels
from kaizen.classify.prompt import CommentInput
from kaizen.db import ActivityLog, Comment, CommentLabel, LabelStatus


class Labeller(Protocol):
    name: str
    version: str

    def label(self, items: Sequence[CommentInput]) -> dict[int, Labels]: ...


@dataclass
class LabelRun:
    labelled: int = 0
    missed: int = 0  # the labeller skipped these ids
    failed_batches: int = 0


def unlabelled(session: Session, limit: int | None = None) -> list[CommentInput]:
    query = (
        select(Comment)
        .outerjoin(CommentLabel, CommentLabel.comment_id == Comment.id)
        .where(CommentLabel.id.is_(None))
        .order_by(Comment.id)
    )
    if limit:
        query = query.limit(limit)
    return [
        CommentInput(id=c.id, text=c.text, source=c.source.value, unit=c.unit)  # text is de-identified
        for c in session.scalars(query)
    ]


def label_comments(
    session: Session,
    labeller: Labeller,
    *,
    batch_size: int = 10,
    workers: int = 4,
    limit: int | None = None,
    user_id: int | None = None,
) -> LabelRun:
    items = unlabelled(session, limit)
    batches = [items[i : i + batch_size] for i in range(0, len(items), batch_size)]
    run = LabelRun()

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        futures = {pool.submit(labeller.label, batch): batch for batch in batches}
        for future in as_completed(futures):
            batch = futures[future]
            try:
                results = future.result()
            except LabelError:
                run.failed_batches += 1
                continue
            for item in batch:
                labels = results.get(item.id)
                if labels is None:
                    run.missed += 1
                    continue
                values = labels.as_dict()
                session.add(
                    CommentLabel(
                        comment_id=item.id,
                        status=LabelStatus.SUGGESTED,
                        suggested=values,
                        labeller=labeller.name,
                        prompt_version=labeller.version,
                        **values,
                    )
                )
                run.labelled += 1
            session.commit()

    session.add(
        ActivityLog(
            user_id=user_id,
            action="label_comments",
            detail={
                "labeller": labeller.name,
                "prompt_version": labeller.version,
                "labelled": run.labelled,
                "missed": run.missed,
                "failed_batches": run.failed_batches,
            },
        )
    )
    session.commit()
    return run
