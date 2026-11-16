"""Build a demo database by running the real pipeline on the synthetic comments.

    python backend/scripts/demo_data.py work/demo.db

Run it from the repository root. Each step uses the same code as the app:

1. Import data/synthetic/comments.csv through the CSV checks and de-identification (FR1, FR2).
2. Label every comment (FR3). By default the TF-IDF baseline is trained on the synthetic
   training split, so no key is needed and nothing is spent. `--labeller llm` uses the
   LiteLLM labeller instead; set KAIZEN_LABEL_MODEL, for example `ollama/qwen2.5:7b` for a
   free local model.
3. Group the labelled comments into ranked issues (FR4), with keyword names, or LLM names
   with `--llm-names`.
4. Create three accounts, demo-qi, demo-manager (unit 4B) and demo-admin, all with the one
   password typed at the prompt, or taken from KAIZEN_DEMO_PASSWORD if that is set. It is
   never printed or saved in plain text.

Then start the API on that database:

    KAIZEN_DATABASE_URL=sqlite:///work/demo.db uvicorn kaizen.api.app:create_app --factory
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import time
from pathlib import Path

from kaizen.api.auth import hash_password
from kaizen.classify.baseline import BaselineLabeller
from kaizen.classify.labels import Labels
from kaizen.classify.prompt import CommentInput
from kaizen.classify.run import label_comments
from kaizen.db import Channel, Comment, Role, User, make_engine, make_sessionmaker
from kaizen.ingest.csv_import import parse_csv
from kaizen.ingest.save import save_feedback
from kaizen.issues.build import build_issues
from kaizen.issues.embed import SentenceEmbedder
from kaizen.issues.name import IssueNamer, KeywordNamer

DATA = Path("data/synthetic")


def baseline_from_training_split(saved: list[Comment]) -> BaselineLabeller:
    """Train on the comments the synthetic truth file marks as training data."""
    truth = [json.loads(line) for line in (DATA / "truth.jsonl").read_text(encoding="utf-8").splitlines() if line]
    if len(truth) != len(saved):
        raise SystemExit(f"{len(saved)} comments imported but truth.jsonl has {len(truth)} rows")
    train = [i for i, t in enumerate(truth) if t["split"] == "train"]
    items = [CommentInput(saved[i].id, saved[i].text, saved[i].source.value, saved[i].unit) for i in train]
    return BaselineLabeller().fit(items, [Labels.model_validate(truth[i]) for i in train])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("database", type=Path, help="new .db file")
    parser.add_argument("--labeller", choices=["baseline", "llm"], default="baseline")
    parser.add_argument("--llm-names", action="store_true", help="name issues with the LLM (KAIZEN_NAME_MODEL)")
    args = parser.parse_args()
    if args.database.suffix != ".db" or args.database.exists():
        parser.error("choose a new .db file")
    password = os.environ.get("KAIZEN_DEMO_PASSWORD") or getpass.getpass("Password for the demo accounts (10 or more characters): ")
    if len(password) < 10:
        parser.error("the password needs at least 10 characters")

    args.database.parent.mkdir(parents=True, exist_ok=True)
    engine = make_engine(f"sqlite:///{args.database.as_posix()}")
    with make_sessionmaker(engine)() as session:
        password_hash = hash_password(password)
        admin = User(username="demo-admin", role=Role.ADMIN, password_hash=password_hash)
        session.add_all([admin, User(username="demo-qi", role=Role.QI, password_hash=password_hash),
                         User(username="demo-manager", role=Role.MANAGER, unit="4B", password_hash=password_hash)])
        session.commit()

        started = time.perf_counter()
        rows, errors = parse_csv((DATA / "comments.csv").read_bytes())
        batch = save_feedback(session, rows, Channel.CSV, admin.id, rows_rejected=len(errors))
        saved = session.query(Comment).filter(Comment.batch_id == batch.id).order_by(Comment.id).all()
        print(f"imported {len(saved)} comments, rejected {len(errors)} ({time.perf_counter() - started:.0f}s)")

        started = time.perf_counter()
        if args.labeller == "baseline":
            labeller = baseline_from_training_split(saved)
            run = label_comments(session, labeller, batch_size=100, workers=1, user_id=admin.id)
        else:
            from kaizen.classify.llm import LLMLabeller

            labeller = LLMLabeller()
            run = label_comments(session, labeller, user_id=admin.id)
        print(f"labelled {run.labelled} with {labeller.name}, failed batches {run.failed_batches} "
              f"({time.perf_counter() - started:.0f}s)")

        started = time.perf_counter()
        namer = IssueNamer() if args.llm_names else KeywordNamer()
        issue_run = build_issues(session, SentenceEmbedder(), namer, user_id=admin.id)
        print(f"built issues from {issue_run.comments_used} comments, smallest issue {issue_run.min_cluster_size}, "
              f"{issue_run.outliers} outliers ({time.perf_counter() - started:.0f}s)")
    engine.dispose()
    print(f"done: KAIZEN_DATABASE_URL=sqlite:///{args.database.as_posix()}")


if __name__ == "__main__":
    main()
