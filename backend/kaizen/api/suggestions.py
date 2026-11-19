"""Suggestion endpoints for QI staff (FR7, NFR2).

Drafting runs one LLM request while the client waits, usually well under a minute. It gives
up after DRAFT_TIMEOUT seconds with no retry, since the person can press Try again. The
drafter (documents, passage vectors and the embedding model) loads on the first request and
is kept in `app.state.drafter`; tests put a fake there.

When the model cannot be used (Ollama not running, a model that was never pulled, no API
key, or no answer in time) the reply is a 503 that says what to do, not a stack trace. Only
the error's type name is logged, never its text or the request.

Nothing the model writes is final: a suggestion stays `suggested` until a person accepts,
edits or rejects it, and every decision is logged with field names only.
"""

from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from kaizen.api.auth import get_session, require
from kaizen.classify.labels import Stage
from kaizen.classify import llm  # imports LiteLLM after kaizen.classify has configured it
from kaizen.classify.llm import CONFIG_ERRORS, limited, unreachable_reason
from kaizen.db import ActivityLog, Issue, Role, Suggestion, SuggestionStatus, User, utcnow
from kaizen.suggest.corpus import CorpusError
from kaizen.suggest.draft import DraftError, SuggestionDrafter
from kaizen.suggest.run import draft_for_issue, load_index

router = APIRouter()
qi = require(Role.QI, Role.ADMIN)

EDITABLE = ("change", "owner", "stage", "measure")
DRAFT_TIMEOUT = 120  # seconds
LOCAL_FIX = "Start Ollama and pull qwen2.5:7b, or set an API key."
logger = logging.getLogger(__name__)


def unreachable_message(reason: str, model: str) -> str:
    """What the QI analyst sees when the model cannot be used, with what to do about it."""
    return {
        "timeout": f"The model did not answer within {DRAFT_TIMEOUT} seconds. Try again, or check that Ollama is running.",
        "connection": f"The model is not reachable. {LOCAL_FIX}",
        "not_found": f"The model {model} is not available. {LOCAL_FIX}",
        "auth": f"The model needs an API key that is missing or wrong. {LOCAL_FIX}",
    }[reason]


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
            drafter = SuggestionDrafter(load_index(), completion=limited(llm.litellm.completion, DRAFT_TIMEOUT, retries=0))
        except CorpusError as exc:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"The documents could not be loaded: {exc}.") from exc
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
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "No documents are loaded, so there is nothing to cite. Add them to documents/."
        )
    try:
        result, rows = draft_for_issue(session, issue, drafter, user.id)
    # reply_text lets a wrong key, model name or request through unwrapped (they stop a
    # labelling run), so catch those here as well as DraftError.
    except (DraftError, *CONFIG_ERRORS) as exc:
        logger.warning("drafting for issue %s failed: %s", issue_id, type(exc.__cause__ or exc).__name__)
        reason = unreachable_reason(exc)
        if reason is not None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, unreachable_message(reason, drafter.model)) from exc
        if isinstance(exc, DraftError):
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"The model gave no usable reply ({exc}). Try again.") from exc
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            f"The model refused the request ({type(exc).__name__}). Check KAIZEN_SUGGEST_MODEL and KAIZEN_SUGGEST_EFFORT.",
        ) from exc
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
