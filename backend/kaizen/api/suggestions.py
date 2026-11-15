"""Suggestion endpoints for QI staff (FR7, NFR2).

Drafting runs one LLM request while the client waits, usually well under a minute. The
drafter (documents, passage vectors and the embedding model) loads on the first request and
is kept in `app.state.drafter`; tests put a fake there.

Nothing the model writes is final: a suggestion stays `suggested` until a person accepts,
edits or rejects it, and every decision is logged with field names only.
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from kaizen.api.auth import get_session, require
from kaizen.classify.labels import Stage
from kaizen.db import ActivityLog, Issue, Role, Suggestion, SuggestionStatus, User, utcnow
from kaizen.suggest.corpus import CorpusError
from kaizen.suggest.draft import DraftError, SuggestionDrafter
from kaizen.suggest.run import draft_for_issue, load_index

router = APIRouter()
qi = require(Role.QI, Role.ADMIN)

EDITABLE = ("change", "owner", "stage", "measure")


class DecisionIn(BaseModel):
    decision: Literal["accept", "edit", "reject"]
    change: str | None = None
    owner: str | None = Field(None, max_length=120)
    stage: Stage | None = None
    measure: str | None = None

    @field_validator("change", "owner", "measure")
    @classmethod
    def _not_blank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("cannot be blank")
        return value.strip() if value else value


def _drafter(request: Request) -> SuggestionDrafter:
    drafter = getattr(request.app.state, "drafter", None)
    if drafter is None:
        try:
            drafter = SuggestionDrafter(load_index())
        except CorpusError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"documents could not be loaded: {exc}") from exc
        request.app.state.drafter = drafter
    return drafter


def _out(s: Suggestion, usernames: dict[int, str]) -> dict:
    return {
        "id": s.id,
        "issue": {"id": s.issue_id, "name": s.issue_name},
        "change": s.change,
        "owner": s.owner,
        "stage": s.stage,
        "measure": s.measure,
        "citations": s.citations,
        "status": s.status.value,
        "decided_by": usernames.get(s.decided_by) if s.decided_by else None,
        "decided_at": s.decided_at.isoformat() if s.decided_at else None,
        "created_at": s.created_at.isoformat(),
    }


def _usernames(session: Session, rows: list[Suggestion]) -> dict[int, str]:
    ids = {s.decided_by for s in rows if s.decided_by}
    if not ids:
        return {}
    return dict(session.execute(select(User.id, User.username).where(User.id.in_(ids))).all())


def _log(session: Session, user: User, action: str, entity_type: str | None, entity_id: int | None, detail: dict) -> None:
    session.add(ActivityLog(user_id=user.id, action=action, entity_type=entity_type, entity_id=entity_id, detail=detail))


@router.post("/issues/{issue_id}/suggestions", status_code=status.HTTP_201_CREATED)
def draft(
    issue_id: int,
    request: Request,
    user: User = Depends(qi),
    session: Session = Depends(get_session),
):
    issue = session.get(Issue, issue_id)
    if issue is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such issue")
    drafter = _drafter(request)
    if not drafter.index.passages:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "no documents loaded, so there is nothing to cite")
    try:
        result, rows = draft_for_issue(session, issue, drafter, user.id)
    except DraftError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"the model gave no usable reply ({exc}), try again") from exc
    return {
        "suggestions": [_out(s, {}) for s in rows],
        "dropped": len(result.dropped),
        "reasons": [reason for _, reason in result.dropped],
    }


@router.get("/issues/{issue_id}/suggestions")
def for_issue(issue_id: int, user: User = Depends(qi), session: Session = Depends(get_session)):
    rows = session.scalars(select(Suggestion).where(Suggestion.issue_id == issue_id).order_by(Suggestion.id.desc())).all()
    names = _usernames(session, rows)
    _log(session, user, "view_suggestions", "issue", issue_id, {"count": len(rows)})
    session.commit()
    return {"suggestions": [_out(s, names) for s in rows]}


@router.get("/suggestions")
def review_queue(
    status_: SuggestionStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(qi),
    session: Session = Depends(get_session),
):
    query = select(Suggestion).order_by(Suggestion.id.desc()).limit(limit).offset(offset)
    if status_ is not None:
        query = query.where(Suggestion.status == status_)
    rows = session.scalars(query).all()
    names = _usernames(session, rows)
    _log(session, user, "view_suggestions", None, None, {"count": len(rows), "status": status_.value if status_ else None})
    session.commit()
    return {"suggestions": [_out(s, names) for s in rows]}


@router.post("/suggestions/{suggestion_id}/decision")
def decide(
    suggestion_id: int,
    body: DecisionIn,
    user: User = Depends(qi),
    session: Session = Depends(get_session),
):
    edits = {field: getattr(body, field) for field in EDITABLE if getattr(body, field) is not None}
    if body.decision == "edit" and not edits:
        raise HTTPException(422, "an edit needs at least one of " + ", ".join(EDITABLE))
    if body.decision != "edit" and edits:
        raise HTTPException(422, 'to change the text, use "edit"')

    s = session.get(Suggestion, suggestion_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "no such suggestion")

    for field, value in edits.items():
        setattr(s, field, value.value if isinstance(value, Stage) else value)
    s.status = {"accept": SuggestionStatus.ACCEPTED, "edit": SuggestionStatus.EDITED, "reject": SuggestionStatus.REJECTED}[body.decision]
    s.decided_by = user.id
    s.decided_at = utcnow()
    _log(session, user, "decide_suggestion", "suggestion", s.id, {"decision": body.decision, "edited": sorted(edits)})
    session.commit()
    return _out(s, {user.id: user.username})
