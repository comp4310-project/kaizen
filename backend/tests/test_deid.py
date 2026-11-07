"""De-identification (FR2). The targets come from P3 Table 9.

These sentences are written by hand and are not in the generated test set, to catch
patterns that only work on our own templates.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kaizen.deid import deidentify
from kaizen.deid.evaluate import MUST_FIND_ALL, evaluate, load
from kaizen.deid.recognizers import luhn_valid

TEST_SET = Path(__file__).parent / "data" / "deid_test_set.jsonl"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Dr. Patel never came back.", "Dr. <PERSON> never came back."),
        ("my daughter Grace was scared", "my daughter <PERSON> was scared"),
        ("Call 807-555-0123 or email j.doe@example.com", "Call <PHONE> or email <EMAIL>"),
        ("OHIP 1234-567-897-AB was on file", "OHIP <HEALTH_CARD> was on file"),
        ("Seen on March 3rd, 2026 and again 03/04/2026.", "Seen on <DATE> and again <DATE>."),
        ("Her MRN is M1234567.", "Her MRN is <RECORD_NUMBER>."),
    ],
)
def test_removes_details(text: str, expected: str) -> None:
    assert deidentify(text).text == expected


@pytest.mark.parametrize(
    "text",
    [
        "Waited 3 days on 4B for a bed, then six hours in the ICU.",
        "Pain was 8/10 and they gave 500 mg at 3am in room 412.",
        "Pt transferred to 5A on Monday. Discharge planned for next week.",
        "Overnight in the Emergency Department since 2019 was the worst.",
        "Nurse Practitioner covering the unit was helpful.",
        "may 2 of the nurses come back later?",
    ],
)
def test_keeps_text_that_is_not_personal(text: str) -> None:
    result = deidentify(text)
    assert result.text == text, result.spans


def test_counts_hold_no_text() -> None:
    result = deidentify("Nurse Rose called 807-555-0199 on May 3.")
    assert result.counts == {"PERSON": 1, "PHONE": 1, "DATE": 1}


def test_luhn() -> None:
    assert luhn_valid("1234567897")
    assert not luhn_valid("1234567890")


def test_targets_on_test_set() -> None:
    """P3 Table 9: 95% overall, every ID, phone and email, under 5% over-removal, no units removed."""
    report = evaluate(load(TEST_SET))
    assert sum(report.total.values()) >= 300
    assert report.recall >= 0.95, report.misses
    for typ in MUST_FIND_ALL:
        assert report.recall_for(typ) == 1.0, [m for m in report.misses if m[1] == typ]
    assert report.over_removal_rate < 0.05, report.extra
    assert report.keep_removed["UNIT"] == 0
