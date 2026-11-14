"""Command line for suggestions (FR7).

Check the documents and build or refresh the cached passage vectors:

    python -m kaizen.suggest index

Draft suggestions for one issue (needs ANTHROPIC_API_KEY for the default model). They are
saved as `suggested` for QI staff to accept, edit or reject:

    python -m kaizen.suggest draft 12

Write the rating sheet for P3 Table 9: 40 Kaizen suggestions from the top issues, the same
number from the same model with no documents, shuffled, plus a key saying which is which.
Give each rater their own copy of the sheet; keep the key away from them:

    python -m kaizen.suggest rating-sheet eval/

Score the filled-in copies against the targets:

    python -m kaizen.suggest score eval/suggestions-key.csv rater1.csv rater2.csv

The documents come from KAIZEN_CORPUS_DIR (default `documents`); see kaizen/suggest/corpus.py
for the file format.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

from kaizen.suggest.corpus import CorpusError
from kaizen.suggest.evaluate import ScoreError


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


def _rating_sheet(args) -> None:
    from kaizen.db import make_engine, make_sessionmaker
    from kaizen.suggest.draft import SuggestionDrafter
    from kaizen.suggest.evaluate import collect, write_sheet
    from kaizen.suggest.run import load_index

    drafter = SuggestionDrafter(load_index())
    if not drafter.index.passages:
        raise SystemExit("no documents loaded, so there is nothing to cite")
    with make_sessionmaker(make_engine())() as session:
        collection = collect(session, drafter, count=args.count)
    sheet, key = write_sheet(collection, args.folder, seed=args.seed)
    summary = {
        "model": collection.model,
        "prompt_version": collection.prompt_version,
        "issues_used": collection.issues_used,
        "items": len(collection.items),
        "kaizen_dropped_by_citation_check": collection.kaizen_dropped,
        "issues_with_no_usable_reply": collection.failed_issues,
        "seed": args.seed,
    }
    (Path(args.folder) / "suggestions-collection.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"{len(collection.items)} suggestions from {collection.issues_used} issues -> {sheet}")
    print(f"key (keep it from the raters) -> {key}")
    print(f"{collection.kaizen_dropped} dropped by the citation check, {collection.failed_issues} issues with no usable reply")


def _score(args) -> None:
    from kaizen.suggest.evaluate import TARGET_SHARE, score

    result = score(args.key, args.sheets)
    k, n = result["kaizen"], result["no_documents"]
    print(f"Kaizen: {k['share_5_or_6']:.0%} score 5 or 6 (target {TARGET_SHARE:.0%}), {k['unsafe']} unsafe: "
          f"{'met' if k['meets_target'] else 'MISSED'}")
    for name, arm in (("Kaizen", k), ("No documents", n)):
        means = ", ".join(f"{c} {'n/a' if v is None else f'{v:.2f}'}" for c, v in arm["mean"].items())
        print(f"{name:13} {arm['suggestions']} suggestions; mean {means}; {arm['unsafe']} unsafe")
    if result["agreement"]:
        for criterion, a in result["agreement"].items():
            kappa = "n/a" if a["kappa"] is None else f"{a['kappa']:.2f}"
            print(f"agreement {criterion:17} exact {a['exact']:.0%}, weighted kappa {kappa}")
    if args.out:
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m kaizen.suggest")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="check the documents and cache their passage vectors").set_defaults(func=_index)
    draft = sub.add_parser("draft", help="draft suggestions for one issue")
    draft.add_argument("issue_id", type=int)
    draft.set_defaults(func=_draft)
    sheet = sub.add_parser("rating-sheet", help="write the P3 Table 9 rating sheet and its key")
    sheet.add_argument("folder", type=Path)
    sheet.add_argument("--count", type=int, default=40, help="Kaizen suggestions to rate")
    sheet.add_argument("--seed", type=int, default=1, help="shuffle order")
    sheet.set_defaults(func=_rating_sheet)
    scored = sub.add_parser("score", help="score filled-in rating sheets against the targets")
    scored.add_argument("key", type=Path)
    scored.add_argument("sheets", type=Path, nargs="+")
    scored.add_argument("--out", type=Path, help="also write the full result as JSON")
    scored.set_defaults(func=_score)
    args = parser.parse_args()
    try:
        args.func(args)
    except CorpusError as exc:
        raise SystemExit(f"documents: {exc}") from exc
    except ScoreError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main()
