"""Score completed human sheets separately from synthetic intent results."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from sklearn.metrics import cohen_kappa_score

from kaizen.classify.labels import Category, Labels
from kaizen.evaluation.report import check, environment, save
from kaizen.evaluation.run import label_metrics
from kaizen.evaluation.ratings import score_issues


def human_labels(path):
    """Read completed exported CSV. Never fill blank fields with predictions."""
    result = {}
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            key = int(row["row_id"])
            if key in result:
                raise ValueError("duplicate row_id in human labels")
            row["categories"] = json.loads(row["categories"])
            result[key] = Labels.model_validate(row)
    if not result:
        raise ValueError("empty human label file")
    return result


def predictions(path):
    result = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        key = int(row["row_id"])
        if key in result:
            raise ValueError("duplicate row_id in predictions")
        result[key] = Labels.model_validate(row["prediction"]) if row["prediction"] is not None else None
    return {k: v for k, v in result.items() if v is not None}


def agreement(first, second):
    if first.keys() != second.keys():
        raise ValueError("both raters must label the same comments")
    ids = sorted(first)
    result = {"comments": len(ids)}
    for field in ("sentiment", "stage", "urgency"):
        a, b = ([getattr(s[i], field).value for i in ids] for s in (first, second))
        # Kappa is undefined for two identical constant lists.
        value = None if len(set(a + b)) == 1 else float(cohen_kappa_score(a, b))
        result[field] = check(value, .6)
    result["categories"] = {}
    for category in Category:
        a, b = ([category in s[i].categories for i in ids] for s in (first, second))
        value = None if len(set(a + b)) == 1 else float(cohen_kappa_score(a, b))
        result["categories"][category.value] = check(value, .6)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    lab = sub.add_parser("labels")
    lab.add_argument("--gold", required=True, type=Path, help="completed, adjudicated 300-row heldout CSV")
    lab.add_argument("--predictions", required=True, type=Path)
    lab.add_argument("--corpus", required=True, choices=["synthetic", "public"])
    lab.add_argument("--model", required=True)
    lab.add_argument("--calibration", type=Path, help="100-row development CSV, checked for overlap")
    lab.add_argument("--human-confirmed", action="store_true", required=True,
                     help="attest that gold labels were completed by people, not generated")
    agree = sub.add_parser("agreement")
    agree.add_argument("raters", type=Path, nargs=2)
    issues = sub.add_parser("issues")
    issues.add_argument("raters", type=Path, nargs=2)
    suggest = sub.add_parser("suggestions")
    suggest.add_argument("--key", type=Path, required=True)
    suggest.add_argument("raters", type=Path, nargs=2)
    for parser in (lab, agree, issues, suggest):
        parser.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    report = {"environment": environment()}
    if args.command == "labels":
        gold = human_labels(args.gold)
        if args.calibration:
            dev_ids = {int(r["row_id"]) for r in csv.DictReader(args.calibration.open(encoding="utf-8-sig"))}
            if dev_ids & gold.keys():
                raise ValueError("calibration and heldout rows overlap")
        report[args.corpus] = label_metrics(gold, predictions(args.predictions))
        report[args.corpus]["model"] = args.model
        report[args.corpus]["annotation_origin"] = "human; caller attestation"
        report[args.corpus]["sample_size"] = check(len(gold), 300, operator="==")
    elif args.command == "agreement":
        report["agreement"] = agreement(*(human_labels(p) for p in args.raters))
        report["agreement"]["sample_size"] = check(report["agreement"]["comments"], 100, operator="==")
    elif args.command == "issues":
        report["human_issue_quality"] = score_issues(args.raters)
    else:
        from kaizen.suggest.evaluate import score
        result = score(args.key, args.raters)
        report["suggestions"] = result
        kaizen = result["kaizen"]
        report["targets"] = {"sample_size": check(kaizen["suggestions"], 40, operator="=="),
                             "unsafe": check(kaizen["unsafe"], 0, operator="=="),
                             "good_share": check(kaizen["share_5_or_6"], .7)}
    save(args.out, report)


if __name__ == "__main__":
    main()
