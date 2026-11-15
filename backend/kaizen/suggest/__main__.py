"""Command line for suggestions (FR7).

Check the documents and build or refresh the cached passage vectors:

    python -m kaizen.suggest index

Draft suggestions for one issue (needs ANTHROPIC_API_KEY for the default model). They are
saved as `suggested` for QI staff to accept, edit or reject:

    python -m kaizen.suggest draft 12

The documents come from KAIZEN_CORPUS_DIR (default `documents`); see kaizen/suggest/corpus.py
for the file format.
"""

from __future__ import annotations

import argparse
from collections import Counter

from kaizen.suggest.corpus import CorpusError


def _index(args) -> None:
    from kaizen.suggest.run import load_index

    index = load_index()
    documents = Counter(p.document_id for p in index.passages)
    print(f"{len(documents)} documents, {len(index.passages)} passages")


def _draft(args) -> None:
    from kaizen.db import Issue, make_engine, make_sessionmaker
    from kaizen.suggest.draft import SuggestionDrafter
    from kaizen.suggest.run import draft_for_issue, load_index

    drafter = SuggestionDrafter(load_index())
    if not drafter.index.passages:
        raise SystemExit("no documents loaded, so there is nothing to cite")
    with make_sessionmaker(make_engine())() as session:
        issue = session.get(Issue, args.issue_id)
        if issue is None:
            raise SystemExit(f"no issue with id {args.issue_id}, see `python -m kaizen.issues build`")
        result, rows = draft_for_issue(session, issue, drafter, user_id=None)
    print(f"{issue.name}: {len(rows)} saved, {len(result.dropped)} dropped ({drafter.name})")
    for row in rows:
        print(f"  [{row.id}] {row.change} (owner: {row.owner})")
    for _, reason in result.dropped:
        print(f"  dropped: {reason}")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m kaizen.suggest")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="check the documents and cache their passage vectors").set_defaults(func=_index)
    draft = sub.add_parser("draft", help="draft suggestions for one issue")
    draft.add_argument("issue_id", type=int)
    draft.set_defaults(func=_draft)
    args = parser.parse_args()
    try:
        args.func(args)
    except CorpusError as exc:
        raise SystemExit(f"documents: {exc}") from exc


if __name__ == "__main__":
    main()
