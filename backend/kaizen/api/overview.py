"""The overview page and the weekly trend of one issue (FR4, FR5).

Weeks are 7-day blocks that end on the newest comment date, not today, the same way
`kaizen.issues.rank` decides whether an issue is rising. That keeps the chart and the
"Rising" flag in agreement, and works on synthetic data from any period.

Unit managers only get counts for their own unit (NFR1).
"""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kaizen.api.auth import get_session, require, unit_scope
from kaizen.api.runs import latest_run, run_out
from kaizen.db import (
    ActivityLog,
    Comment,
    CommentLabel,
    ImportBatch,
    Issue,
    IssueComment,
    IssueRun,
    LabelStatus,
    Role,
    Source,
    User,
)
from kaizen.issues.rank import RISING_FACTOR, RISING_MIN_COMMENTS

router = APIRouter()
readers = require(Role.QI, Role.ADMIN, Role.MANAGER)

OVERVIEW_WEEKS = 12
MAX_TREND_WEEKS = 52


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def weekly(rows: list[tuple[date, Source]], as_of: date, weeks: int) -> list[dict]:
    """Counts per 7-day block ending on `as_of`, oldest first. Week 0 is as_of - 6 to as_of."""
    counts: dict[int, Counter] = {}
    for day, source in rows:
        back = (as_of - day).days // 7
        if 0 <= back < weeks:
            counts.setdefault(back, Counter())[source] += 1
    out = []
    for back in range(weeks - 1, -1, -1):
        end = as_of - timedelta(days=7 * back)
        c = counts.get(back, Counter())
        out.append({
            "start": (end - timedelta(days=6)).isoformat(),
            "end": end.isoformat(),
            "patient": c[Source.PATIENT_FAMILY],
            "staff": c[Source.STAFF],
        })
    return out


def _count(session: Session, query) -> int:
    return session.scalar(select(func.count()).select_from(query.subquery()))


@router.get("/overview")
def overview(request: Request, user: User = Depends(readers), session: Session = Depends(get_session)):
    unit = unit_scope(user, None)
    comments = select(Comment.id, Comment.source, Comment.feedback_date, Comment.created_at)
    if unit:
        comments = comments.where(Comment.unit == unit)
    scoped = comments.subquery()

    total = session.scalar(select(func.count()).select_from(scoped))
    by_source = dict(session.execute(select(scoped.c.source, func.count()).group_by(scoped.c.source)).all())
    labelled = session.scalar(
        select(func.count()).select_from(scoped).join(CommentLabel, CommentLabel.comment_id == scoped.c.id)
    )
    confirmed = session.scalar(
        select(func.count())
        .select_from(scoped)
        .join(CommentLabel, CommentLabel.comment_id == scoped.c.id)
        .where(CommentLabel.status == LabelStatus.CONFIRMED)
    )
    as_of = session.scalar(select(func.max(scoped.c.feedback_date)))
    weeks = []
    if as_of:
        since = as_of - timedelta(days=7 * OVERVIEW_WEEKS - 1)
        rows = session.execute(
            select(scoped.c.feedback_date, scoped.c.source).where(scoped.c.feedback_date >= since)
        ).all()
        weeks = weekly([(d, s) for d, s in rows], as_of, OVERVIEW_WEEKS)

    if unit:
        last_import = session.scalar(select(func.max(scoped.c.created_at)))
    else:
        last_import = session.scalar(select(func.max(ImportBatch.created_at)))

    run = session.scalar(select(IssueRun).order_by(IssueRun.id.desc()).limit(1))
    issues_out = {"count": 0, "rising": 0, "top": []}
    new_since_run = total
    if run is not None:
        issues = session.scalars(select(Issue).where(Issue.run_id == run.id).order_by(Issue.rank)).all()
        unit_sizes = None
        if unit:
            unit_sizes = dict(session.execute(
                select(IssueComment.issue_id, func.count())
                .join(Comment, Comment.id == IssueComment.comment_id)
                .join(Issue, Issue.id == IssueComment.issue_id)
                .where(Issue.run_id == run.id, Comment.unit == unit)
                .group_by(IssueComment.issue_id)
            ).all())
            issues = [i for i in issues if i.id in unit_sizes]
        issues_out = {
            "count": len(issues),
            "rising": sum(i.rising for i in issues),
            "top": [
                {
                    "id": i.id,
                    "rank": i.rank,
                    "name": i.name,
                    "size": i.size,
                    "unit_size": unit_sizes[i.id] if unit_sizes is not None else None,
                    "negative_share": i.negative_share,
                    "rising": i.rising,
                }
                for i in issues[:3]
            ],
        }
        new_since_run = session.scalar(
            select(func.count()).select_from(scoped).where(scoped.c.created_at > run.created_at)
        )

    process = None
    if user.role in (Role.QI, Role.ADMIN):
        process = run_out(latest_run(session, request.app.state.run_lock))

    session.add(ActivityLog(user_id=user.id, action="view_overview", detail={"unit": unit}))
    session.commit()
    return {
        "unit": unit,
        "comments": {
            "total": total,
            "labelled": labelled,
            "unlabelled": total - labelled,
            "confirmed": confirmed,
            "patient": by_source.get(Source.PATIENT_FAMILY, 0),
            "staff": by_source.get(Source.STAFF, 0),
            "new_since_run": new_since_run,
        },
        "run": None if run is None else {
            "id": run.id,
            "created_at": _iso(run.created_at),
            "as_of": _iso(run.as_of),
            "comments_used": run.comments_used,
        },
        "issues": issues_out,
        "weeks_as_of": _iso(as_of),
        "weeks": weeks,
        "last_import": _iso(last_import),
        "process": process,
    }


@router.get("/issues/{issue_id}/trend")
def issue_trend(issue_id: int, user: User = Depends(readers), session: Session = Depends(get_session)):
    """Weekly comment counts for one issue, by source, from its first comment to the run's newest date.

    `last_week` and `prior_weeks` are counted over the whole issue, whatever the unit, so they
    explain the issue's own rising flag: rising means at least 3 comments in the last 7 days and
    at least twice the weekly average of the 28 days before. For a manager the weekly counts
    are their unit's only.
    """
    issue = session.get(Issue, issue_id)
    unit = unit_scope(user, None)
    rows = []
    if issue is not None:
        rows = session.execute(
            select(Comment.feedback_date, Comment.source, Comment.unit)
            .join(IssueComment, IssueComment.comment_id == Comment.id)
            .where(IssueComment.issue_id == issue_id)
        ).all()
    scoped = [(d, s) for d, s, u in rows if not unit or u == unit]
    if issue is None or not scoped:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such issue")

    run = session.get(IssueRun, issue.run_id)
    as_of = (run.as_of if run else None) or max(d for d, _, _ in rows)
    first = min(d for d, _ in scoped)
    n_weeks = min(MAX_TREND_WEEKS, (as_of - first).days // 7 + 1)

    week_start = as_of - timedelta(days=6)
    before_start = week_start - timedelta(days=28)
    last_week = sum(week_start <= d <= as_of for d, _, _ in rows)
    prior = sum(before_start <= d < week_start for d, _, _ in rows)

    session.add(ActivityLog(user_id=user.id, action="view_issue_trend", entity_type="issue", entity_id=issue_id,
                            detail={"unit": unit}))
    session.commit()
    return {
        "issue": {"id": issue.id, "rank": issue.rank, "name": issue.name},
        "unit": unit,
        "as_of": as_of.isoformat(),
        "weeks": weekly(scoped, as_of, n_weeks),
        "rising": issue.rising,
        "last_week": last_week,
        "prior_weeks": prior,
        "prior_weekly_average": round(prior / 4, 2),
        "rising_min_comments": RISING_MIN_COMMENTS,
        "rising_factor": RISING_FACTOR,
    }
