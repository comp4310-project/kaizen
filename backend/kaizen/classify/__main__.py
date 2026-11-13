"""Command line for labelling (FR3).

Label every saved comment that has no labels yet (needs ANTHROPIC_API_KEY):

    python -m kaizen.classify label

Score a labeller against a hand-labelled file (P3 Table 9):

    python -m kaizen.classify evaluate gold.jsonl --method claude
    python -m kaizen.classify evaluate gold.jsonl --method baseline --train synthetic.jsonl

Each line of a labelled file is a JSON object with `text`, `source` ("patient_family" or
"staff"), `sentiment`, `categories`, `stage` and `urgency`, and optionally `id` and `unit`.
The text must already be de-identified.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from kaizen.classify.labels import Labels
from kaizen.classify.metrics import TARGETS, score
from kaizen.classify.prompt import CommentInput


def load_labelled(path: Path) -> tuple[list[CommentInput], dict[int, Labels]]:
    items, labels = [], {}
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        comment_id = int(row.get("id", n))
        items.append(CommentInput(id=comment_id, text=row["text"], source=row["source"], unit=row.get("unit", "")))
        labels[comment_id] = Labels.model_validate(row)
    return items, labels


def _label(args) -> None:
    from kaizen.classify.claude import ClaudeLabeller
    from kaizen.classify.run import label_comments
    from kaizen.db import make_engine, make_sessionmaker

    labeller = ClaudeLabeller()
    with make_sessionmaker(make_engine())() as session:
        run = label_comments(session, labeller, batch_size=args.batch_size, workers=args.workers, limit=args.limit)
    print(f"{labeller.name}: labelled {run.labelled}, skipped by model {run.missed}, failed batches {run.failed_batches}")


def _evaluate(args) -> None:
    items, gold = load_labelled(args.gold)
    if args.method == "baseline":
        if not args.train:
            raise SystemExit("--train is needed for the baseline")
        from kaizen.classify.baseline import BaselineLabeller

        train_items, train_labels = load_labelled(args.train)
        labeller = BaselineLabeller().fit(train_items, [train_labels[i.id] for i in train_items])
        predicted = labeller.label(items)
    else:
        from kaizen.classify.claude import ClaudeLabeller, LabelError

        labeller = ClaudeLabeller()
        predicted = {}
        for i in range(0, len(items), args.batch_size):
            try:
                predicted.update(labeller.label(items[i : i + args.batch_size]))
            except LabelError as exc:
                print(f"batch starting at {i} failed: {exc}")

    result = score(gold, predicted)
    result["labeller"] = labeller.name
    result["prompt_version"] = labeller.version
    for name, target in TARGETS.items():
        value = result[name]
        shown = "n/a" if value is None else f"{value:.3f}"
        print(f"{name:22} {shown:>6}  target {target:.2f}  {'met' if result['meets_target'][name] else 'MISSED'}")
    print(f"{'category_macro_f1':22} {result['category_macro_f1']:.3f}")
    print(f"{'stage_macro_f1':22} {result['stage_macro_f1']:.3f}   unclear rate {result['stage_unclear_rate']:.2f}")
    print(f"comments {result['comments']}, missing predictions {result['missing']}")
    if args.out:
        args.out.write_text(json.dumps(result, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m kaizen.classify")
    sub = parser.add_subparsers(dest="command", required=True)

    label = sub.add_parser("label", help="label saved comments that have no labels yet")
    label.add_argument("--limit", type=int)
    label.add_argument("--batch-size", type=int, default=10)
    label.add_argument("--workers", type=int, default=4)
    label.set_defaults(func=_label)

    evaluate = sub.add_parser("evaluate", help="score a labeller against hand labels")
    evaluate.add_argument("gold", type=Path)
    evaluate.add_argument("--method", choices=["claude", "baseline"], default="claude")
    evaluate.add_argument("--train", type=Path, help="labelled file to train the baseline on")
    evaluate.add_argument("--batch-size", type=int, default=10)
    evaluate.add_argument("--out", type=Path, help="also write the full result as JSON")
    evaluate.set_defaults(func=_evaluate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
