"""Command line for issue finding (FR4).

Group the saved, labelled comments into ranked issues. Names come from Claude when
ANTHROPIC_API_KEY is set; --keyword-names skips Claude and names issues from keywords:

    python -m kaizen.issues build [--min-size 8] [--keyword-names]

Write the rating sheet for the newest run (P3 Table 9):

    python -m kaizen.issues rating-sheet issues-to-rate.csv

Check how many built-in problems a labelled synthetic file recovers. Each line is a JSON
object with `text`, `source`, `sentiment`, `urgency`, `stage`, `categories`, `date`
(YYYY-MM-DD) and `planted` (the built-in problem's name, or null):

    python -m kaizen.issues recovery synthetic.jsonl
"""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from kaizen.issues.rank import IssueComment


def _build(args) -> None:
    from kaizen.db import make_engine, make_sessionmaker
    from kaizen.issues.build import build_issues
    from kaizen.issues.embed import SentenceEmbedder
    from kaizen.issues.name import IssueNamer, KeywordNamer

    namer = KeywordNamer() if args.keyword_names else IssueNamer()
    with make_sessionmaker(make_engine())() as session:
        run = build_issues(session, SentenceEmbedder(), namer, min_cluster_size=args.min_size)
        print(f"run {run.id}: {run.comments_used} comments, {run.outliers} outliers")
        from sqlalchemy import select

        from kaizen.db import Issue

        for issue in session.scalars(select(Issue).where(Issue.run_id == run.id).order_by(Issue.rank).limit(15)):
            flag = "  RISING" if issue.rising else ""
            print(f"{issue.rank:3}. {issue.name} ({issue.size} comments, score {issue.score}){flag}")


def _rating_sheet(args) -> None:
    from kaizen.db import make_engine, make_sessionmaker
    from kaizen.issues.evaluate import rating_sheet

    with make_sessionmaker(make_engine())() as session:
        n = rating_sheet(session, args.out)
    print(f"wrote {n} issues to {args.out}")


def _recovery(args) -> None:
    from kaizen.issues.embed import SentenceEmbedder
    from kaizen.issues.evaluate import planted_recovery
    from kaizen.issues.pipeline import find_issues

    texts, comments, planted = [], [], []
    for n, line in enumerate(args.file.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row["sentiment"] == "positive":
            continue  # issues are built from negative and neutral comments only
        texts.append(row["text"])
        planted.append(row.get("planted"))
        comments.append(
            IssueComment(
                id=n,
                source=row["source"],
                sentiment=row["sentiment"],
                urgency=row["urgency"],
                stage=row["stage"],
                categories=tuple(row.get("categories", [])),
                feedback_date=date.fromisoformat(row["date"]),
            )
        )
    found, outliers = find_issues(texts, comments, SentenceEmbedder().embed(texts), args.min_size)
    result = planted_recovery(found, planted)
    print(f"found {result['found']} of {result['planted']} built-in problems in the top 15 (target 6 of 8)")
    for problem, rank in result["rank_of"].items():
        print(f"  {problem}: {'rank ' + str(rank) if rank else 'not found'}")
    print(f"{len(found)} issues, {len(outliers)} outliers out of {len(texts)} comments")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m kaizen.issues")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="group labelled comments into ranked issues")
    build.add_argument("--min-size", type=int, default=8, help="smallest group that counts as an issue")
    build.add_argument("--keyword-names", action="store_true", help="name issues from keywords, without Claude")
    build.set_defaults(func=_build)

    sheet = sub.add_parser("rating-sheet", help="CSV of top issues for two members to rate")
    sheet.add_argument("out", type=Path)
    sheet.set_defaults(func=_rating_sheet)

    recovery = sub.add_parser("recovery", help="check a labelled synthetic file for its built-in problems")
    recovery.add_argument("file", type=Path)
    recovery.add_argument("--min-size", type=int, default=8)
    recovery.set_defaults(func=_recovery)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
