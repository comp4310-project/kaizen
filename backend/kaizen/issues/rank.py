"""Scores issues so the QI team sees the most pressing ones first (FR4).

score = comments x (0.5 + negative share) x (1 + high-urgency share)

Volume counts most. An issue that is all negative counts three times as much as one that is
all neutral, and one where every comment is high urgency counts double. Urgency uses the
current label, which is the person's answer once it has been confirmed (FR6).

An issue is rising (a Could item in P3) when its last 7 days have at least 3 comments and at
least twice its weekly average over the 4 weeks before. "Last 7 days" ends at the newest
comment date in the data, not today, so it works on synthetic data from any period.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Sequence

RISING_MIN_COMMENTS = 3
RISING_FACTOR = 2.0


@dataclass(frozen=True)
class IssueComment:
    """What ranking needs from one labelled comment."""

    id: int
    source: str  # "patient_family" or "staff"
    sentiment: str
    urgency: str
    stage: str
    categories: tuple[str, ...]
    feedback_date: date


@dataclass(frozen=True)
class IssueStats:
    size: int
    negative_share: float
    high_share: float
    patient_count: int
    staff_count: int
    main_stage: str
    top_categories: list[str]
    recent_count: int
    rising: bool
    score: float


def issue_stats(comments: Sequence[IssueComment], as_of: date) -> IssueStats:
    size = len(comments)
    negative_share = sum(c.sentiment == "negative" for c in comments) / size
    high_share = sum(c.urgency == "high" for c in comments) / size
    sources = Counter(c.source for c in comments)
    stages = Counter(c.stage for c in comments)
    categories = Counter(cat for c in comments for cat in c.categories)

    week_start = as_of - timedelta(days=6)
    before_start = week_start - timedelta(days=28)
    recent = sum(week_start <= c.feedback_date <= as_of for c in comments)
    before = sum(before_start <= c.feedback_date < week_start for c in comments)
    rising = recent >= RISING_MIN_COMMENTS and recent >= RISING_FACTOR * (before / 4)

    return IssueStats(
        size=size,
        negative_share=round(negative_share, 3),
        high_share=round(high_share, 3),
        patient_count=sources.get("patient_family", 0),
        staff_count=sources.get("staff", 0),
        # Ties go to the alphabetically first stage, so results are repeatable.
        main_stage=min(stages, key=lambda s: (-stages[s], s)),
        top_categories=[c for c, _ in sorted(categories.items(), key=lambda kv: (-kv[1], kv[0]))[:3]],
        recent_count=recent,
        rising=rising,
        score=round(size * (0.5 + negative_share) * (1 + high_share), 2),
    )
