"""Validate two independent issue-rating sheets, then score the P3 rubric."""
import csv
from collections import defaultdict
from pathlib import Path

from kaizen.evaluation.report import check


def score_issues(paths):
    if len(paths) != 2:
        raise ValueError("two independent rater files are required")
    sheets = []
    for path in paths:
        rows = list(csv.DictReader(Path(path).open(encoding="utf-8-sig", newline="")))
        items = {}
        for row in rows:
            key = (int(row["rank"]), int(row["comment_id"]))
            if key in items:
                raise ValueError("duplicate issue/comment rating")
            values = (row["same_problem (y/n)"].strip().lower(), row["name_is_specific (y/n)"].strip().lower())
            if any(v not in ("y", "n") for v in values):
                raise ValueError("both rating fields must be y or n on every row")
            items[key] = values
        sheets.append(items)
    if not sheets[0] or sheets[0].keys() != sheets[1].keys():
        raise ValueError("raters must score the same nonempty sample")
    grouped = defaultdict(list)
    for key in sheets[0]:
        grouped[key[0]].append(key)
    good = 0
    for keys in grouped.values():
        if len(keys) != 10:
            raise ValueError("P3 requires ten comments per rated issue")
        # Conservative agreement rule: both raters must find >=8 matching and a specific name.
        good += all(sum(sheet[k][0] == "y" for k in keys) >= 8 and
                    all(sheet[k][1] == "y" for k in keys) for sheet in sheets)
    return {"issues": len(grouped), "good": good, "raters": 2,
            "good_share": check(good / len(grouped), .70),
            "scope": "top 15" if len(grouped) == 15 else "partial: fewer than 15 issues",
            "exact_row_agreement": sum(sheets[0][k] == sheets[1][k] for k in sheets[0]) / len(sheets[0])}
