"""The FastAPI app: login, feedback import and the public form (FR1, NFR1).

    uvicorn kaizen.api.app:create_app --factory --reload

Set KAIZEN_DATABASE_URL to use MySQL, for example
mysql+pymysql://kaizen:password@localhost:3306/kaizen. The default is a local SQLite file.
"""

from __future__ import annotations

from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kaizen.api.auth import current_user, get_session, hash_password, issue_token, require, verify_password
from kaizen.api.issues import router as issues_router
from kaizen.api.suggestions import router as suggestions_router
from kaizen.db import ActivityLog, Channel, Comment, Role, Source, User, make_engine, make_sessionmaker
from kaizen.ingest.csv_import import CsvFormatError, check_row, parse_csv
from kaizen.ingest.save import save_feedback
from kaizen.units import UNITS, is_known_unit

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_ERRORS_RETURNED = 100


class LoginIn(BaseModel):
    username: str
    password: str


class FeedbackIn(BaseModel):
    # Plain strings so our own checks give the error, rather than FastAPI echoing the input.
    text: str = ""
    source: str = ""
    unit: str = ""
    date: str = ""


class UserIn(BaseModel):
    username: str
    password: str
    role: Role
    unit: str | None = None


def log(session: Session, user: User | None, action: str, entity_type=None, entity_id=None, detail=None) -> None:
    session.add(
        ActivityLog(
            user_id=user.id if user else None,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            detail=detail,
        )
    )


def create_app(database_url: str | None = None) -> FastAPI:
    app = FastAPI(title="Kaizen", version="0.1.0")
    app.state.sessionmaker = make_sessionmaker(make_engine(database_url))
    app.include_router(issues_router)
    app.include_router(suggestions_router)

    @app.post("/auth/login")
    def login(body: LoginIn, session: Session = Depends(get_session)):
        user = session.scalar(select(User).where(User.username == body.username))
        if user is None or not user.active or not verify_password(body.password, user.password_hash):
            log(session, None, "login_failed")
            session.commit()
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "wrong username or password")
        token = issue_token(session, user)
        log(session, user, "login")
        session.commit()
        return {"token": token, "role": user.role.value, "unit": user.unit}

    @app.get("/units")
    def units():
        return [{"code": code, "name": name} for code, name in UNITS.items()]

    @app.post("/feedback", status_code=status.HTTP_201_CREATED)
    def submit_feedback(body: FeedbackIn, session: Session = Depends(get_session)):
        """The public form. No login, so anyone can submit; spam protection is out of scope."""
        row, reason = check_row(body.text, body.source, body.unit, body.date or date.today().isoformat())
        if row is None:
            raise HTTPException(422, reason)
        batch = save_feedback(session, [row], Channel.FORM, user_id=None)
        return {"batch_id": batch.id}

    @app.post("/imports", status_code=status.HTTP_201_CREATED)
    def import_csv(
        file: UploadFile,
        user: User = Depends(require(Role.QI, Role.ADMIN)),
        session: Session = Depends(get_session),
    ):
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, "file is over 5MB, split it")
        try:
            rows, errors = parse_csv(data)
        except CsvFormatError as exc:
            raise HTTPException(422, str(exc)) from exc
        batch = save_feedback(session, rows, Channel.CSV, user.id, rows_rejected=len(errors))
        return {
            "batch_id": batch.id,
            "saved": len(rows),
            "rejected": len(errors),
            "errors": [{"line": e.line, "reason": e.reason} for e in errors[:MAX_ERRORS_RETURNED]],
        }

    @app.get("/comments")
    def list_comments(
        unit: str | None = None,
        source: Source | None = None,
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        user: User = Depends(require(Role.QI, Role.ADMIN, Role.MANAGER)),
        session: Session = Depends(get_session),
    ):
        """De-identified comments. Unit managers only see their own unit (NFR1)."""
        if user.role is Role.MANAGER:
            if unit and unit.upper() != user.unit:
                raise HTTPException(status.HTTP_403_FORBIDDEN, "managers can only view their own unit")
            unit = user.unit
        query = select(Comment)
        if unit:
            query = query.where(Comment.unit == unit.upper())
        if source:
            query = query.where(Comment.source == source)
        total = session.scalar(select(func.count()).select_from(query.subquery()))
        comments = session.scalars(query.order_by(Comment.id).limit(limit).offset(offset)).all()
        log(session, user, "view_comments", detail={"unit": unit, "source": source and source.value, "count": len(comments)})
        session.commit()
        return {
            "total": total,
            "comments": [
                {
                    "id": c.id,
                    "source": c.source.value,
                    "unit": c.unit,
                    "date": c.feedback_date.isoformat(),
                    "text": c.text,
                }
                for c in comments
            ],
        }

    @app.post("/users", status_code=status.HTTP_201_CREATED)
    def create_user(
        body: UserIn,
        admin: User = Depends(require(Role.ADMIN)),
        session: Session = Depends(get_session),
    ):
        if body.role is Role.MANAGER and not (body.unit and is_known_unit(body.unit)):
            raise HTTPException(422, "a unit manager needs a unit from the unit list")
        if len(body.password) < 10:
            raise HTTPException(422, "password must be at least 10 characters")
        if session.scalar(select(User).where(User.username == body.username)):
            raise HTTPException(status.HTTP_409_CONFLICT, "username is taken")
        user = User(
            username=body.username,
            password_hash=hash_password(body.password),
            role=body.role,
            unit=body.unit.upper() if body.unit else None,
        )
        session.add(user)
        session.flush()
        log(session, admin, "create_user", "user", user.id, {"role": body.role.value})
        session.commit()
        return {"id": user.id}

    @app.get("/me")
    def me(user: User = Depends(current_user)):
        return {"username": user.username, "role": user.role.value, "unit": user.unit}

    return app
