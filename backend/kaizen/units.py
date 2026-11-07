"""The fixed list of hospital units that feedback can be recorded against (FR1).

Draft list for the synthetic data. The team agrees the final list in week 1. Codes are
what the CSV `unit` column holds. Names and codes are also protected from
de-identification, because the unit filters need them (FR2).
"""

from __future__ import annotations

import re
from functools import lru_cache

UNITS: dict[str, str] = {
    "ED": "Emergency Department",
    "ICU": "Intensive Care Unit",
    "2A": "General Surgery",
    "3A": "Cardiology",
    "4A": "General Medicine",
    "4B": "General Medicine",
    "5A": "Orthopedics",
    "6A": "Adult Mental Health",
}

# Other ways people write a unit in free text.
_EXTRA_NAMES = ("Emergency", "ER", "Intensive Care", "Surgery", "Orthopaedics", "Mental Health")


@lru_cache(maxsize=1)
def unit_mention_pattern() -> re.Pattern[str]:
    """Matches a unit name or code in free text, with an optional "ward" or "unit" in front."""
    terms = sorted({*UNITS, *UNITS.values(), *_EXTRA_NAMES}, key=len, reverse=True)
    alternatives = "|".join(re.escape(t) for t in terms)
    return re.compile(rf"\b(?:(?:ward|unit)\s+)?(?:{alternatives})\b", re.IGNORECASE)


def is_known_unit(code: str) -> bool:
    return code.strip().upper() in UNITS
