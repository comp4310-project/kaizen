"""Scores de-identification against the test set (P3 Table 9).

    python -m kaizen.deid.evaluate tests/data/deid_test_set.jsonl

A detail counts as found only if every character of it is covered by a tag, since half
a name is still a leak. The tag type does not have to match: a health card number tagged
as a phone number is still removed. A tag that touches no personal detail counts as
over-removal.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from kaizen.deid.deidentify import Span, find_spans

# Types that must all be found (Table 9). Names and dates only count toward the 95%.
MUST_FIND_ALL = ("PHONE", "EMAIL", "HEALTH_CARD", "RECORD_NUMBER")


@dataclass
class Report:
    found: Counter = field(default_factory=Counter)
    total: Counter = field(default_factory=Counter)
    tags: int = 0
    over_removed: int = 0
    keep_removed: Counter = field(default_factory=Counter)
    keep_total: Counter = field(default_factory=Counter)
    misses: list[tuple[int, str, str]] = field(default_factory=list)
    extra: list[tuple[int, str]] = field(default_factory=list)

    @property
    def recall(self) -> float:
        return sum(self.found.values()) / max(1, sum(self.total.values()))

    @property
    def over_removal_rate(self) -> float:
        return self.over_removed / max(1, self.tags)

    def recall_for(self, typ: str) -> float:
        return self.found[typ] / max(1, self.total[typ])


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def _covered(start: int, end: int, spans: list[Span]) -> bool:
    chars = set(range(start, end))
    for s in spans:
        chars -= set(range(s.start, s.end))
    return not chars


def _overlaps(start: int, end: int, s: Span) -> bool:
    return s.start < end and start < s.end


def evaluate(items: list[dict], detect: Callable[[str], list[Span]] = find_spans) -> Report:
    report = Report()
    for item in items:
        text, spans = item["text"], detect(item["text"])
        report.tags += len(spans)
        for d in item["details"]:
            report.total[d["type"]] += 1
            if _covered(d["start"], d["end"], spans):
                report.found[d["type"]] += 1
            else:
                report.misses.append((item["id"], d["type"], text[d["start"] : d["end"]]))
        for s in spans:
            if not any(_overlaps(d["start"], d["end"], s) for d in item["details"]):
                report.over_removed += 1
                report.extra.append((item["id"], text[s.start : s.end]))
        for k in item["keep"]:
            report.keep_total[k["type"]] += 1
            if any(_overlaps(k["start"], k["end"], s) for s in spans):
                report.keep_removed[k["type"]] += 1
    return report


def print_report(report: Report) -> None:
    print(f"{'type':<15}{'found':>8}{'total':>8}{'recall':>9}")
    for typ in sorted(report.total):
        print(f"{typ:<15}{report.found[typ]:>8}{report.total[typ]:>8}{report.recall_for(typ):>9.1%}")
    print(f"{'overall':<15}{sum(report.found.values()):>8}{sum(report.total.values()):>8}{report.recall:>9.1%}")
    print(f"\nover-removal: {report.over_removed} of {report.tags} tags ({report.over_removal_rate:.1%})")
    for typ in sorted(report.keep_total):
        print(f"{typ} removed: {report.keep_removed[typ]} of {report.keep_total[typ]}")
    if report.misses:
        print("\nmissed:")
        for item_id, typ, text in report.misses:
            print(f"  #{item_id} {typ}: {text!r}")
    if report.extra:
        print("\nremoved but not personal:")
        for item_id, text in report.extra:
            print(f"  #{item_id} {text!r}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("test_set", type=Path)
    args = parser.parse_args()
    print_report(evaluate(load(args.test_set)))


if __name__ == "__main__":
    main()
