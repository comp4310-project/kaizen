"""Builds the ranked issue list from saved, labelled comments (FR4).

Only comments that describe a problem are grouped: negative or neutral, with at least one
problem category. Praise is left out, and so are non-answers like "Nothing" or "Did not
answer", which are neutral with no category. On the real FFT comments those non-answers
formed six of the seven issues, each with an invented name. A model can still give a
non-answer a category, so the usual survey non-answers are also dropped by their text. Comments that have no labels yet are skipped, so run the labeller first. Each run
is kept, and the dashboard shows the newest one.
"""

from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from kaizen.db import ActivityLog, Comment, CommentLabel, Issue, IssueComment, IssueRun
from kaizen.issues.embed import Embedder
from kaizen.issues.pipeline import default_min_size, find_issues
from kaizen.issues.rank import IssueComment as RankInput


# Whole-comment answers that say nothing about the service, as they appear in the FFT data.
_NON_ANSWER = re.compile(
    r"(nothing( at all| really| else| to add| to improve)?|no(ne|pe)?|not really|n/?a|nil|ok(ay)?"
    r"|did not answer|no comments?|can ?not think of anything|can'?t think of anything|see (above|previous))"
)


def is_non_answer(text: str) -> bool:
    return bool(_NON_ANSWER.fullmatch(re.sub(r"[^\w/' ]+", " ", text.lower()).strip()))


def load(session: Session) -> tuple[list[int], list[str], list[RankInput]]:
    rows = session.execute(
        select(Comment, CommentLabel)
        .join(CommentLabel, CommentLabel.comment_id == Comment.id)
        .where(CommentLabel.sentiment != "positive")
        .order_by(Comment.id)
    ).all()
    rows = [(c, lab) for c, lab in rows if lab.categories and not is_non_answer(c.text)]
    ids = [c.id for c, _ in rows]
    texts = [c.text for c, _ in rows]  # de-identified
    comments = [
        RankInput(
            id=c.id,
            source=c.source.value,
            sentiment=lab.sentiment,
            urgency=lab.urgency,
            stage=lab.stage,
            categories=tuple(lab.categories),
            feedback_date=c.feedback_date,
        )
        for c, lab in rows
    ]
    return ids, texts, comments


def build_issues(
    session: Session,
    embedder: Embedder,
    namer,
    *,
    min_cluster_size: int | None = None,
    seed: int = 42,
    user_id: int | None = None,
) -> IssueRun:
    ids, texts, comments = load(session)
    # None means the default: 2% of the comments being grouped, at least 8.
    min_cluster_size = min_cluster_size or default_min_size(len(texts))
    vectors = embedder.embed(texts) if texts else None
    found, outliers = find_issues(texts, comments, vectors, min_cluster_size, seed) if texts else ([], [])

    run = IssueRun(
        embedder=embedder.name,
        namer=namer.name,
        min_cluster_size=min_cluster_size,
        comments_used=len(texts),
        outliers=len(outliers),
        as_of=max((c.feedback_date for c in comments), default=None),
        created_by=user_id,
    )
    session.add(run)
    session.flush()

    for rank, item in enumerate(found, start=1):
        cluster, stats = item.cluster, item.stats
        name = namer.name_issue(cluster.keywords, [texts[i] for i in cluster.representatives])
        issue = Issue(
            run_id=run.id,
            rank=rank,
            name=name[:120],
            keywords=cluster.keywords,
            size=stats.size,
            negative_share=stats.negative_share,
            high_share=stats.high_share,
            patient_count=stats.patient_count,
            staff_count=stats.staff_count,
            main_stage=stats.main_stage,
            top_categories=stats.top_categories,
            recent_count=stats.recent_count,
            rising=stats.rising,
            score=stats.score,
        )
        session.add(issue)
        session.flush()
        typical = set(cluster.representatives)
        session.add_all(
            IssueComment(issue_id=issue.id, comment_id=ids[i], typical=i in typical) for i in cluster.members
        )

    session.add(
        ActivityLog(
            user_id=user_id,
            action="build_issues",
            entity_type="issue_run",
            entity_id=run.id,
            detail={"issues": len(found), "comments_used": len(texts), "outliers": len(outliers)},
        )
    )
    session.commit()
    return run
