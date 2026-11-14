"""Read endpoints for the issues dashboard (FR4, FR8).

Both show the newest issue run. Unit managers only see issues that include comments from
their own unit, and only those comments (NFR1).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kaizen.api.auth import get_session, require
from kaizen.db import ActivityLog, Comment, CommentLabel, Issue, IssueComment, IssueRun, Role, User

router = APIRouter()
readers = require(Role.QI, Role.ADMIN, Role.MANAGER)


def _unit_counts(session: Session, run_id: int, unit: str) -> dict[int, int]:
    rows = session.execute(
        select(IssueComment.issue_id, func.count())
        .join(Comment, Comment.id == IssueComment.comment_id)
        .join(Issue, Issue.id == IssueComment.issue_id)
        .where(Issue.run_id == run_id, Comment.unit == unit)
        .group_by(IssueComment.issue_id)
    ).all()
    return dict(rows)


@router.get("/issues")
def list_issues(
    limit: int = Query(30, ge=1, le=200),
    user: User = Depends(readers),
    session: Session = Depends(get_session),
):
    run = session.scalar(select(IssueRun).order_by(IssueRun.id.desc()).limit(1))
    if run is None:
        return {"run": None, "issues": []}

    issues = session.scalars(select(Issue).where(Issue.run_id == run.id).order_by(Issue.rank)).all()
    unit_counts = _unit_counts(session, run.id, user.unit) if user.role is Role.MANAGER else None
    if unit_counts is not None:
        issues = [i for i in issues if i.id in unit_counts]
    issues = issues[:limit]

    session.add(ActivityLog(user_id=user.id, action="view_issues", entity_type="issue_run", entity_id=run.id, detail={"count": len(issues)}))
    session.commit()
    return {
        "run": {
            "id": run.id,
            "created_at": run.created_at.isoformat(),
            "as_of": run.as_of.isoformat() if run.as_of else None,
            "comments_used": run.comments_used,
            "outliers": run.outliers,
        },
        "issues": [
            {
                "id": i.id,
                "rank": i.rank,
                "name": i.name,
                "keywords": i.keywords,
                "size": i.size,
                "unit_size": unit_counts[i.id] if unit_counts is not None else None,
                "negative_share": i.negative_share,
                "high_share": i.high_share,
                "patient_count": i.patient_count,
                "staff_count": i.staff_count,
                "main_stage": i.main_stage,
                "top_categories": i.top_categories,
                "recent_count": i.recent_count,
                "rising": i.rising,
                "score": i.score,
            }
            for i in issues
        ],
    }


@router.get("/issues/{issue_id}/comments")
def issue_comments(
    issue_id: int,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(readers),
    session: Session = Depends(get_session),
):
    """The de-identified comments behind one issue, most typical first, with their labels."""
    issue = session.get(Issue, issue_id)
    query = (
        select(Comment, CommentLabel, IssueComment.typical)
        .join(IssueComment, IssueComment.comment_id == Comment.id)
        .outerjoin(CommentLabel, CommentLabel.comment_id == Comment.id)
        .where(IssueComment.issue_id == issue_id)
    )
    if user.role is Role.MANAGER:
        query = query.where(Comment.unit == user.unit)
    total = session.scalar(select(func.count()).select_from(query.subquery())) if issue else 0
    if issue is None or (total == 0 and user.role is Role.MANAGER):
        # Same answer whether the issue doesn't exist or belongs to another unit.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such issue")

    rows = session.execute(query.order_by(IssueComment.typical.desc(), Comment.id).limit(limit).offset(offset)).all()
    session.add(
        ActivityLog(user_id=user.id, action="view_issue_comments", entity_type="issue", entity_id=issue_id, detail={"count": len(rows)})
    )
    session.commit()
    return {
        "issue": {"id": issue.id, "rank": issue.rank, "name": issue.name},
        "total": total,
        "comments": [
            {
                "id": c.id,
                "source": c.source.value,
                "unit": c.unit,
                "date": c.feedback_date.isoformat(),
                "text": c.text,
                "typical": typical,
                "labels": None
                if label is None
                else {
                    "sentiment": label.sentiment,
                    "categories": label.categories,
                    "stage": label.stage,
                    "urgency": label.urgency,
                    "status": label.status.value,
                },
            }
            for c, label, typical in rows
        ],
    }
