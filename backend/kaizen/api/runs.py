"""Process new feedback from the app: label every unlabelled comment, then rebuild issues (FR3, FR4).

Uploads and the public form only save comments. Before this, labelling and grouping needed
`python -m kaizen.classify label` and `python -m kaizen.issues build` on the server.

`POST /runs` starts one run in a background thread and returns at once; `GET /runs/latest`
reports how it is going. Only one run at a time: a second POST while one is queued or running
gets 409. The thread opens its own database session, since a SQLAlchemy session must not be
shared between threads.

Labelling uses the TF-IDF baseline trained on the synthetic training split, unless
KAIZEN_LABEL_MODEL is set, in which case the LLM labeller is used. Issue names come from
keywords unless KAIZEN_NAME_MODEL is set.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from kaizen.api.auth import get_session, require
from kaizen.db import ActivityLog, Comment, CommentLabel, Issue, ProcessRun, ProcessStatus, Role, User, utcnow

router = APIRouter()
runners = require(Role.QI, Role.ADMIN)


@dataclass
class Pipeline:
    """What a run uses. Tests swap in fakes through `app.state.pipeline`."""

    labeller: Callable[[], object]
    embedder: Callable[[], object]
    namer: Callable[[], object]


def default_pipeline() -> Pipeline:
    def labeller():
        if os.environ.get("KAIZEN_LABEL_MODEL"):
            from kaizen.classify.llm import LLMLabeller

            return LLMLabeller()
        from kaizen.classify.synthetic import synthetic_baseline

        return synthetic_baseline()

    def embedder():
        from kaizen.issues.embed import SentenceEmbedder

        return SentenceEmbedder()

    def namer():
        from kaizen.issues.name import IssueNamer, KeywordNamer

        return IssueNamer() if os.environ.get("KAIZEN_NAME_MODEL") else KeywordNamer()

    return Pipeline(labeller, embedder, namer)


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def run_out(run: ProcessRun | None) -> dict | None:
    if run is None:
        return None
    return {
        "id": run.id,
        "status": run.status.value,
        "labeller": run.labeller,
        "to_label": run.to_label,
        "labelled": run.labelled,
        "failed_batches": run.failed_batches,
        "issue_run_id": run.issue_run_id,
        "issues": run.issues,
        "comments_used": run.comments_used,
        "error": run.error,
        "created_at": _iso(run.created_at),
        "started_at": _iso(run.started_at),
        "finished_at": _iso(run.finished_at),
    }


def _close_abandoned(session: Session, lock: threading.Lock) -> None:
    """A run left queued or running while no thread holds the lock died with an earlier server."""
    if lock.locked():
        return
    stale = session.scalars(
        select(ProcessRun).where(ProcessRun.status.in_([ProcessStatus.QUEUED, ProcessStatus.RUNNING]))
    ).all()
    for run in stale:
        run.status = ProcessStatus.FAILED
        run.error = "the server stopped before this run finished"
        run.finished_at = utcnow()
    if stale:
        session.commit()


def latest_run(session: Session, lock: threading.Lock) -> ProcessRun | None:
    _close_abandoned(session, lock)
    return session.scalar(select(ProcessRun).order_by(ProcessRun.id.desc()).limit(1))


def _process(make_session: sessionmaker, pipeline: Pipeline, run_id: int, user_id: int, lock: threading.Lock) -> None:
    from kaizen.classify.run import label_comments
    from kaizen.issues.build import build_issues

    try:
        with make_session() as session:
            run = session.get(ProcessRun, run_id)
            run.status = ProcessStatus.RUNNING
            run.started_at = utcnow()
            session.commit()
            try:
                labeller = pipeline.labeller()
                run.labeller = labeller.name
                session.commit()
                labelled = label_comments(session, labeller, batch_size=100 if labeller.name == "tfidf-logreg" else 10,
                                          workers=1 if labeller.name == "tfidf-logreg" else 4, user_id=user_id)
                run.labelled = labelled.labelled
                run.failed_batches = labelled.failed_batches
                session.commit()

                issue_run = build_issues(session, pipeline.embedder(), pipeline.namer(), user_id=user_id)
                run.issue_run_id = issue_run.id
                run.issues = session.scalar(select(func.count()).select_from(Issue).where(Issue.run_id == issue_run.id))
                run.comments_used = issue_run.comments_used
                run.status = ProcessStatus.DONE
            except Exception as exc:  # reported on the page; the message never includes comment text
                session.rollback()
                run = session.get(ProcessRun, run_id)
                run.status = ProcessStatus.FAILED
                run.error = f"{type(exc).__name__}: {exc}"[:500]
            run.finished_at = utcnow()
            session.add(
                ActivityLog(
                    user_id=user_id,
                    action="process_feedback_done" if run.status is ProcessStatus.DONE else "process_feedback_failed",
                    entity_type="process_run",
                    entity_id=run_id,
                    detail={"labelled": run.labelled, "issues": run.issues, "issue_run": run.issue_run_id},
                )
            )
            session.commit()
    finally:
        lock.release()


@router.post("/runs", status_code=status.HTTP_202_ACCEPTED)
def start_run(request: Request, user: User = Depends(runners), session: Session = Depends(get_session)):
    """Labels every unlabelled comment and rebuilds issues in the background. 409 if a run is going."""
    lock: threading.Lock = request.app.state.run_lock
    _close_abandoned(session, lock)
    if not lock.acquire(blocking=False):
        raise HTTPException(status.HTTP_409_CONFLICT, "a run is already in progress, wait for it to finish")
    try:
        to_label = session.scalar(
            select(func.count())
            .select_from(Comment)
            .outerjoin(CommentLabel, CommentLabel.comment_id == Comment.id)
            .where(CommentLabel.id.is_(None))
        )
        run = ProcessRun(status=ProcessStatus.QUEUED, to_label=to_label, created_by=user.id)
        session.add(run)
        session.flush()
        session.add(ActivityLog(user_id=user.id, action="process_feedback", entity_type="process_run",
                                entity_id=run.id, detail={"to_label": to_label}))
        session.commit()
        thread = threading.Thread(
            target=_process,
            args=(request.app.state.sessionmaker, request.app.state.pipeline, run.id, user.id, lock),
            name=f"process-run-{run.id}",
            daemon=True,
        )
        thread.start()
    except BaseException:
        lock.release()
        raise
    request.app.state.run_thread = thread
    return run_out(run)


@router.get("/runs/latest")
def get_latest(request: Request, user: User = Depends(runners), session: Session = Depends(get_session)):
    """The newest run, or null if the app has never processed feedback."""
    return {"run": run_out(latest_run(session, request.app.state.run_lock))}
