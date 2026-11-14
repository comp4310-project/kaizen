"""Checks the issue list against the P3 Table 9 targets for issues (FR4).

Two checks:

1. Built-in problems. The synthetic data plants 8 known problems. One counts as found when
   an issue in the top 15 is at least half made of that problem's comments and holds at
   least 30% of them. Target: 6 of 8.
2. A rating sheet for two members: 10 random comments from each of the top 15 issues. An
   issue is good when at least 8 of its 10 are about the same problem and its name names a
   specific process. Target: 70% of issues good.
"""

from __future__ import annotations

import csv
import random
from collections import Counter
from pathlib import Path
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kaizen.db import Comment, Issue, IssueComment, IssueRun
from kaizen.issues.pipeline import FoundIssue

TOP_N = 15
PURITY = 0.5
COVERAGE = 0.3


def planted_recovery(found: Sequence[FoundIssue], planted: Sequence[str | None], top_n: int = TOP_N) -> dict:
    """Which built-in problems the top issues recover. `planted` has one entry per comment."""
    totals = Counter(p for p in planted if p)
    result: dict[str, int | None] = {p: None for p in sorted(totals)}
    for rank, issue in enumerate(found[:top_n], start=1):
        members = [planted[i] for i in issue.cluster.members]
        counts = Counter(p for p in members if p)
        if not counts:
            continue
        problem, n = counts.most_common(1)[0]
        if n / len(members) >= PURITY and n / totals[problem] >= COVERAGE and result[problem] is None:
            result[problem] = rank
    return {"found": sum(r is not None for r in result.values()), "planted": len(result), "rank_of": result}


def rating_sheet(session: Session, path: Path, top_n: int = TOP_N, per_issue: int = 10, seed: int = 1) -> int:
    """Writes the newest run's rating sheet as CSV. Returns the number of issues on it."""
    run_id = session.scalar(select(func.max(IssueRun.id)))
    if run_id is None:
        raise SystemExit("no issue run yet, run `python -m kaizen.issues build` first")
    issues = session.scalars(select(Issue).where(Issue.run_id == run_id, Issue.rank <= top_n).order_by(Issue.rank)).all()
    rng = random.Random(seed)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "issue_name", "comment_id", "comment", "same_problem (y/n)", "name_is_specific (y/n)"])
        for issue in issues:
            comment_ids = session.scalars(select(IssueComment.comment_id).where(IssueComment.issue_id == issue.id)).all()
            sample = sorted(rng.sample(list(comment_ids), min(per_issue, len(comment_ids))))
            texts = dict(session.execute(select(Comment.id, Comment.text).where(Comment.id.in_(sample))).all())
            for n, comment_id in enumerate(sample):
                writer.writerow([issue.rank, issue.name if n == 0 else "", comment_id, texts[comment_id], "", ""])
    return len(issues)
