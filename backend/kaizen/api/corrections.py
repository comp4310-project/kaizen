"""Corrections by QI staff: labels, redaction, and renaming or merging issues (FR6).

Every change adds an activity_log row with field names, ids and counts only. The log never
holds comment text, a redacted span, or an issue name (NFR1).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from kaizen.api.auth import get_session, require
from kaizen.classify.labels import Category, Sentiment, Stage, Urgency
from kaizen.db import (
    ActivityLog,
    Comment,
    CommentLabel,
    Issue,
    IssueComment,
    IssueRun,
    LabelStatus,
    Role,
    Suggestion,
    User,
    utcnow,
)
from kaizen.issues.rank import IssueComment as RankInput
from kaizen.issues.rank import issue_stats

router = APIRouter()
qi = require(Role.QI, Role.ADMIN)

REDACTED = "<REDACTED>"


class LabelsIn(BaseModel):
    """Leave every field out to confirm the labels as they are."""

    sentiment: Sentiment | None = None
    categories: list[Category] | None = None
    stage: Stage | None = None
    urgency: Urgency | None = None


class RedactIn(BaseModel):
    start: int = Field(ge=0)
    end: int = Field(ge=0)


class RenameIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)

    @field_validator("name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("cannot be blank")
        return value.strip()


class MergeIn(BaseModel):
    into: int


def _log(session: Session, user: User, action: str, entity_type: str, entity_id: int, detail: dict) -> None:
    session.add(ActivityLog(user_id=user.id, action=action, entity_type=entity_type, entity_id=entity_id, detail=detail))


def _labels_out(label: CommentLabel) -> dict:
    return {
        "comment_id": label.comment_id,
        "sentiment": label.sentiment,
        "categories": label.categories,
        "stage": label.stage,
        "urgency": label.urgency,
        "status": label.status.value,
        "suggested": label.suggested,
        "confirmed_by": label.confirmed_by,
        "confirmed_at": label.confirmed_at.isoformat() if label.confirmed_at else None,
    }


@router.post("/comments/{comment_id}/labels")
def confirm_labels(
    comment_id: int,
    body: LabelsIn,
    user: User = Depends(qi),
    session: Session = Depends(get_session),
):
    """Confirm the labels, or correct any of them. `suggested` is never changed."""
    label = session.scalar(select(CommentLabel).where(CommentLabel.comment_id == comment_id))
    if label is None:
        if session.get(Comment, comment_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "no such comment")
        raise HTTPException(status.HTTP_409_CONFLICT, "this comment has no labels yet, run the labeller first")

    new = {}
    if body.sentiment is not None:
        new["sentiment"] = body.sentiment.value
    if body.categories is not None:
        new["categories"] = sorted({c.value for c in body.categories})
    if body.stage is not None:
        new["stage"] = body.stage.value
    if body.urgency is not None:
        new["urgency"] = body.urgency.value
    changed = sorted(field for field, value in new.items() if getattr(label, field) != value)

    for field in changed:
        setattr(label, field, new[field])
    label.status = LabelStatus.CONFIRMED
    label.confirmed_by = user.id
    label.confirmed_at = utcnow()
    _log(session, user, "correct_labels" if changed else "confirm_labels", "comment", comment_id, {"changed": changed})
    session.commit()
    return _labels_out(label)


@router.post("/comments/{comment_id}/redact")
def redact(
    comment_id: int,
    body: RedactIn,
    user: User = Depends(qi),
    session: Session = Depends(get_session),
):
    """Replace a personal detail that de-identification missed with <REDACTED>.

    `start` and `end` are character offsets into the stored, already de-identified text,
    as returned by GET /comments, with `end` exclusive (Python slicing).
    """
    comment = session.get(Comment, comment_id)
    if comment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such comment")
    if body.end <= body.start or body.end > len(comment.text):
        raise HTTPException(422, f"the range must have start < end <= {len(comment.text)}, the length of the text")

    comment.text = comment.text[: body.start] + REDACTED + comment.text[body.end :]
    counts = dict(comment.deid_counts or {})
    counts["REDACTED"] = counts.get("REDACTED", 0) + 1
    comment.deid_counts = counts  # a new dict, so SQLAlchemy sees the JSON change
    _log(session, user, "redact_comment", "comment", comment_id, {"length": body.end - body.start})
    session.commit()
    return {"id": comment.id, "text": comment.text}


@router.post("/issues/{issue_id}/rename")
def rename_issue(
    issue_id: int,
    body: RenameIn,
    user: User = Depends(qi),
    session: Session = Depends(get_session),
):
    issue = session.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such issue")
    issue.name = body.name
    _log(session, user, "rename_issue", "issue", issue_id, {"changed": ["name"]})
    session.commit()
    return {"id": issue.id, "rank": issue.rank, "name": issue.name}


def _member_inputs(session: Session, issue_id: int) -> list[RankInput]:
    rows = session.execute(
        select(Comment, CommentLabel)
        .join(IssueComment, IssueComment.comment_id == Comment.id)
        .join(CommentLabel, CommentLabel.comment_id == Comment.id)
        .where(IssueComment.issue_id == issue_id)
    ).all()
    return [
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


@router.post("/issues/{issue_id}/merge")
def merge_issue(
    issue_id: int,
    body: MergeIn,
    user: User = Depends(qi),
    session: Session = Depends(get_session),
):
    """Merge this issue into `into`, then delete this one. Both must be from the same run.

    The comments move across and the target's counts, shares, stage, categories, score and
    rising flag are recomputed with kaizen.issues.rank.issue_stats, from the current labels.
    The issues in the run are then re-ranked by score. Not recomputed: the target keeps its
    own name and keywords (rename it if needed), and each comment keeps its `typical` flag,
    so the merged issue can have more than 10 typical comments.
    """
    if body.into == issue_id:
        raise HTTPException(422, "an issue cannot be merged into itself")
    source = session.get(Issue, issue_id)
    target = session.get(Issue, body.into)
    if source is None or target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such issue")
    if source.run_id != target.run_id:
        raise HTTPException(422, "both issues must come from the same issue run")

    target_ids = select(IssueComment.comment_id).where(IssueComment.issue_id == target.id)
    session.execute(delete(IssueComment).where(IssueComment.issue_id == source.id, IssueComment.comment_id.in_(target_ids)))
    moved = session.execute(
        update(IssueComment).where(IssueComment.issue_id == source.id).values(issue_id=target.id)
    ).rowcount
    # Suggestions keep their own copy of the issue, so point them at the merged one.
    session.execute(update(Suggestion).where(Suggestion.issue_id == source.id).values(issue_id=target.id))
    session.delete(source)
    session.flush()

    run = session.get(IssueRun, target.run_id)
    members = _member_inputs(session, target.id)
    if members:
        as_of = run.as_of or max(m.feedback_date for m in members)
        stats = issue_stats(members, as_of)
        for field in (
            "size",
            "negative_share",
            "high_share",
            "patient_count",
            "staff_count",
            "main_stage",
            "top_categories",
            "recent_count",
            "rising",
            "score",
        ):
            setattr(target, field, getattr(stats, field))

    # Same order as kaizen.issues.pipeline, with the old rank breaking ties.
    issues = session.scalars(select(Issue).where(Issue.run_id == target.run_id)).all()
    for rank, issue in enumerate(sorted(issues, key=lambda i: (-i.score, -i.size, i.rank)), start=1):
        issue.rank = rank

    _log(session, user, "merge_issue", "issue", target.id, {"merged": issue_id, "moved": moved})
    session.commit()
    return {
        "id": target.id,
        "rank": target.rank,
        "name": target.name,
        "size": target.size,
        "patient_count": target.patient_count,
        "staff_count": target.staff_count,
        "score": target.score,
    }
