"""Database tables for import, accounts and the activity log (FR1, FR6, NFR1).

MySQL in Docker for the app, SQLite in tests. Only de-identified text is ever stored: the
`comments.text` column is written from `DeidResult.text` and nothing else. See
docs/data-model.md for the tables other members will add.
"""

from __future__ import annotations

import enum
import os
from datetime import date, datetime, timezone

from sqlalchemy import JSON, Date, DateTime, Enum, ForeignKey, Index, Integer, String, Text, create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

DEFAULT_URL = "sqlite:///./kaizen-dev.db"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    QI = "qi"
    MANAGER = "manager"
    ADMIN = "admin"


class Source(str, enum.Enum):
    PATIENT_FAMILY = "patient_family"
    STAFF = "staff"


class Channel(str, enum.Enum):
    CSV = "csv"
    FORM = "form"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(100))
    role: Mapped[Role] = mapped_column(Enum(Role, values_callable=lambda e: [m.value for m in e]))
    unit: Mapped[str | None] = mapped_column(String(8))  # required for managers
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuthToken(Base):
    """Login sessions. Only a SHA-256 hash of the token is stored."""

    __tablename__ = "auth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ImportBatch(Base):
    """One CSV upload or one form submission. The file name is not kept, since it can hold a name."""

    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    channel: Mapped[Channel] = mapped_column(Enum(Channel, values_callable=lambda e: [m.value for m in e]))
    uploaded_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    rows_saved: Mapped[int] = mapped_column(default=0)
    rows_rejected: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_unit_date", "unit", "feedback_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"))
    source: Mapped[Source] = mapped_column(Enum(Source, values_callable=lambda e: [m.value for m in e]), index=True)
    unit: Mapped[str] = mapped_column(String(8))
    feedback_date: Mapped[date] = mapped_column(Date)
    text: Mapped[str] = mapped_column(Text)  # de-identified only
    deid_counts: Mapped[dict] = mapped_column(JSON, default=dict)  # e.g. {"PERSON": 2}, no values
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActivityLog(Base):
    """Who viewed or changed what (NFR1). `detail` must never hold comment text."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))  # None for the public form
    action: Mapped[str] = mapped_column(String(40), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[int | None] = mapped_column(Integer)
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class LabelStatus(str, enum.Enum):
    SUGGESTED = "suggested"  # from the model, not yet checked
    CONFIRMED = "confirmed"  # a person checked it (FR6)


class CommentLabel(Base):
    """The four labels for one comment (FR3). Values are the strings in kaizen.classify.labels.

    The current values can be corrected by a person (FR6). `suggested` keeps what the model
    first said, so model accuracy can still be measured after corrections.
    """

    __tablename__ = "comment_labels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("comments.id"), unique=True)
    sentiment: Mapped[str] = mapped_column(String(16), index=True)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    stage: Mapped[str] = mapped_column(String(32), index=True)
    urgency: Mapped[str] = mapped_column(String(8), index=True)
    status: Mapped[LabelStatus] = mapped_column(
        Enum(LabelStatus, values_callable=lambda e: [m.value for m in e]), default=LabelStatus.SUGGESTED
    )
    suggested: Mapped[dict] = mapped_column(JSON)
    labeller: Mapped[str] = mapped_column(String(64))  # e.g. "anthropic/claude-haiku-5-5/low" or "tfidf-logreg"
    prompt_version: Mapped[str] = mapped_column(String(16))
    confirmed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class IssueRun(Base):
    """One run of issue finding (FR4). The dashboard shows the newest run."""

    __tablename__ = "issue_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    embedder: Mapped[str] = mapped_column(String(80))
    namer: Mapped[str] = mapped_column(String(64))
    min_cluster_size: Mapped[int] = mapped_column(Integer)
    comments_used: Mapped[int] = mapped_column(Integer)
    outliers: Mapped[int] = mapped_column(Integer)
    as_of: Mapped[date | None] = mapped_column(Date)  # newest comment date, for the rising flag
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Issue(Base):
    """A recurring problem: a group of similar comments with a name and a rank (FR4)."""

    __tablename__ = "issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("issue_runs.id"), index=True)
    rank: Mapped[int] = mapped_column(Integer)  # 1 is the most pressing
    name: Mapped[str] = mapped_column(String(120))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    size: Mapped[int] = mapped_column(Integer)
    negative_share: Mapped[float] = mapped_column()
    high_share: Mapped[float] = mapped_column()
    patient_count: Mapped[int] = mapped_column(Integer)
    staff_count: Mapped[int] = mapped_column(Integer)
    main_stage: Mapped[str] = mapped_column(String(32))
    top_categories: Mapped[list] = mapped_column(JSON, default=list)
    recent_count: Mapped[int] = mapped_column(Integer)
    rising: Mapped[bool] = mapped_column(default=False)
    score: Mapped[float] = mapped_column()


class IssueComment(Base):
    """Which comments belong to an issue. `typical` marks the ones closest to its centre."""

    __tablename__ = "issue_comments"

    issue_id: Mapped[int] = mapped_column(ForeignKey("issues.id"), primary_key=True)
    comment_id: Mapped[int] = mapped_column(ForeignKey("comments.id"), primary_key=True, index=True)
    typical: Mapped[bool] = mapped_column(default=False)


class SuggestionStatus(str, enum.Enum):
    SUGGESTED = "suggested"  # drafted by the model, nobody has decided yet (NFR2)
    ACCEPTED = "accepted"
    EDITED = "edited"  # accepted after a person changed it
    REJECTED = "rejected"


class Suggestion(Base):
    """One cited improvement suggestion for an issue (FR7).

    Every `issues build` makes new issue rows, so a suggestion keeps a copy of the issue it was
    drafted for (name, keywords, comment ids) and still makes sense after a rebuild. `drafted`
    keeps what the model first wrote, so suggestions can still be scored after a person edits
    them (P3 Table 9).
    """

    __tablename__ = "suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    issue_id: Mapped[int | None] = mapped_column(ForeignKey("issues.id"), index=True)  # the issue row at drafting time
    issue_name: Mapped[str] = mapped_column(String(120))
    issue_keywords: Mapped[list] = mapped_column(JSON, default=list)
    issue_comment_ids: Mapped[list] = mapped_column(JSON, default=list)
    change: Mapped[str] = mapped_column(Text)
    owner: Mapped[str] = mapped_column(String(120))
    stage: Mapped[str] = mapped_column(String(32))
    measure: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSON)  # passage id, document id, title, heading, quote
    status: Mapped[SuggestionStatus] = mapped_column(
        Enum(SuggestionStatus, values_callable=lambda e: [m.value for m in e]), default=SuggestionStatus.SUGGESTED, index=True
    )
    drafted: Mapped[dict] = mapped_column(JSON)
    model: Mapped[str] = mapped_column(String(80))  # e.g. "anthropic/claude-opus-5-5/medium"
    prompt_version: Mapped[str] = mapped_column(String(16))
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


def make_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("KAIZEN_DATABASE_URL", DEFAULT_URL)
    kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {"pool_pre_ping": True}
    return create_engine(url, **kwargs)


def make_sessionmaker(engine: Engine) -> sessionmaker:
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
