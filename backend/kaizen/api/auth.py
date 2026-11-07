"""Passwords, login tokens and role checks (NFR1)."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from kaizen.db import AuthToken, Role, User, utcnow

TOKEN_LIFETIME = timedelta(hours=12)
_bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), password_hash.encode())


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(session: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    session.add(AuthToken(token_hash=_hash_token(token), user_id=user.id, expires_at=utcnow() + TOKEN_LIFETIME))
    return token


def get_session(request: Request):
    session = request.app.state.sessionmaker()
    try:
        yield session
    finally:
        session.close()


def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    session: Session = Depends(get_session),
) -> User:
    unauthorised = HTTPException(status.HTTP_401_UNAUTHORIZED, "log in first", {"WWW-Authenticate": "Bearer"})
    if credentials is None:
        raise unauthorised
    row = session.scalar(select(AuthToken).where(AuthToken.token_hash == _hash_token(credentials.credentials)))
    if row is None:
        raise unauthorised
    expires = row.expires_at if row.expires_at.tzinfo else row.expires_at.replace(tzinfo=timezone.utc)
    if expires < datetime.now(timezone.utc):
        raise unauthorised
    user = session.get(User, row.user_id)
    if user is None or not user.active:
        raise unauthorised
    return user


def require(*roles: Role):
    def check(user: User = Depends(current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "your role cannot do this")
        return user

    return check
