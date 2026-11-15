"""Create a fresh, synthetic SQLite database for one NFR4 study session."""

from __future__ import annotations

import argparse
import getpass
from datetime import date
from pathlib import Path

from kaizen.api.auth import hash_password
from kaizen.db import (
    Channel, Comment, CommentLabel, ImportBatch, Issue, IssueComment, IssueRun,
    Role, Source, User, make_engine, make_sessionmaker,
)

OBSERVED = date(2026, 10, 5)
GROUPS = [
    (
        "Delayed discharge instructions",
        "discharge_and_transfers",
        "communication",
        [
            (Source.STAFF, "4B", "Staff had to wait for the instructions before ending the shift."),
            (Source.STAFF, "4B", "The discharge summary was unavailable at handoff."),
            (Source.PATIENT_FAMILY, "4B", "We waited for the printed instructions before leaving."),
            (Source.PATIENT_FAMILY, "3A", "The instructions did not explain the follow-up appointment."),
        ],
    ),
    (
        "Night noise on the ward",
        "care_on_the_ward",
        "environment",
        [
            (Source.PATIENT_FAMILY, "4B", "The corridor noise kept interrupting my sleep."),
            (Source.PATIENT_FAMILY, "3A", "The ward was noisy after lights out."),
        ],
    ),
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("database", type=Path, help="new .db path for this session")
    args = parser.parse_args()
    path = args.database.resolve()
    if path.suffix != ".db" or path.exists():
        parser.error("choose a new .db file")
    password = getpass.getpass("Study password (10 or more characters): ")
    if len(password) < 10 or len(password.encode()) > 72:
        parser.error("use a password of at least 10 characters and at most 72 bytes")
    path.touch(exist_ok=False)
    engine = make_engine(f"sqlite:///{path.as_posix()}")
    try:
        with make_sessionmaker(engine).begin() as session:
            password_hash = hash_password(password)
            session.add_all([
                User(username="study-qi", role=Role.QI, password_hash=password_hash),
                User(username="study-manager", role=Role.MANAGER, unit="4B", password_hash=password_hash),
            ])
            count = sum(len(rows) for _, _, _, rows in GROUPS)
            batch = ImportBatch(channel=Channel.CSV, rows_saved=count)
            run = IssueRun(embedder="synthetic", namer="synthetic", min_cluster_size=2,
                           comments_used=count, outliers=0, as_of=OBSERVED)
            session.add_all([batch, run])
            session.flush()

            for rank, (name, stage, category, rows) in enumerate(GROUPS, 1):
                staff = sum(source == Source.STAFF for source, _, _ in rows)
                issue = Issue(
                    run_id=run.id, rank=rank, name=name, size=len(rows), patient_count=len(rows) - staff,
                    staff_count=staff, negative_share=1, high_share=0, main_stage=stage,
                    top_categories=[category], recent_count=len(rows), score=1.5 * len(rows),
                )
                session.add(issue)
                session.flush()
                labels = {"stage": stage, "categories": [category], "sentiment": "negative", "urgency": "low"}
                for source, unit, text in rows:
                    comment = Comment(batch_id=batch.id, source=source, unit=unit, feedback_date=OBSERVED, text=text)
                    session.add(comment)
                    session.flush()
                    session.add_all([
                        CommentLabel(comment_id=comment.id, suggested=labels, labeller="synthetic",
                                     prompt_version="study", **labels),
                        IssueComment(issue_id=issue.id, comment_id=comment.id, typical=True),
                    ])
    finally:
        engine.dispose()
    print(f"Created synthetic study database at {path}")


if __name__ == "__main__":
    main()
