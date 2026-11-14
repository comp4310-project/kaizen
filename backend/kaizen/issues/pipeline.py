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


def find_issues(
    texts: Sequence[str],
    comments: Sequence[IssueComment],
    vectors: np.ndarray,
    min_cluster_size: int = 8,
    seed: int = 42,
) -> tuple[list[FoundIssue], list[int]]:
    """Issues ordered by score (most pressing first), and the outlier positions."""
    clusters, outliers = find_clusters(texts, vectors, min_cluster_size=min_cluster_size, seed=seed)
    if not comments:
        return [], outliers
    as_of = max(c.feedback_date for c in comments)
    found = [FoundIssue(c, issue_stats([comments[i] for i in c.members], as_of)) for c in clusters]
    found.sort(key=lambda f: (-f.stats.score, -f.stats.size, f.cluster.members[0]))
    return found, outliers
