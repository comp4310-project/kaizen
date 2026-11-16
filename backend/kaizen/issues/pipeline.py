"""Finds and ranks issues from labelled comments, without touching the database (FR4).

`build.py` runs this on saved comments; `evaluate.py` runs it on a labelled file to check
whether the problems built into the synthetic data are found.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np

from kaizen.issues.cluster import Cluster, find_clusters
from kaizen.issues.rank import IssueComment, IssueStats, issue_stats


@dataclass
class FoundIssue:
    cluster: Cluster  # member positions refer to the input lists
    stats: IssueStats


# The smallest issue is 2% of the comments being grouped, and never fewer than 8. A fixed 8
# split 2,300 synthetic comments into 121 small issues and found none of the 8 built-in
# problems. The 2% was chosen on the separate 1,200-comment fixture
# (backend/tests/data/synthetic.jsonl), where anything from 1% to 4% found 7 of 8 and a fixed
# 8 found 3. See docs/decisions.md.
MIN_ISSUE_SIZE = 8
ISSUE_SHARE = 0.02


def default_min_size(n_comments: int) -> int:
    return max(MIN_ISSUE_SIZE, round(n_comments * ISSUE_SHARE))


def find_issues(
    texts: Sequence[str],
    comments: Sequence[IssueComment],
    vectors: np.ndarray,
    min_cluster_size: int | None = None,
    seed: int = 42,
) -> tuple[list[FoundIssue], list[int]]:
    """Issues ordered by score (most pressing first), and the outlier positions."""
    if min_cluster_size is None:
        min_cluster_size = default_min_size(len(texts))
    clusters, outliers = find_clusters(texts, vectors, min_cluster_size=min_cluster_size, seed=seed)
    if not comments:
        return [], outliers
    as_of = max(c.feedback_date for c in comments)
    found = [FoundIssue(c, issue_stats([comments[i] for i in c.members], as_of)) for c in clusters]
    found.sort(key=lambda f: (-f.stats.score, -f.stats.size, f.cluster.members[0]))
    return found, outliers
