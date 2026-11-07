"""Feedback import (FR1). P3 check: a 1,000-row file loads and bad rows are reported."""

from __future__ import annotations

import csv
import io

import pytest

from kaizen.ingest.csv_import import CsvFormatError, parse_csv
from tests.conftest import login


def make_csv(rows: list[dict], header=("text", "source", "unit", "date")) -> bytes:
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=header, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue().encode("utf-8")


GOOD = {"text": "Waited 3 days for discharge meds.", "source": "patient", "unit": "4B", "date": "2026-10-01"}


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"text": "  "}, "text is empty"),
        ({"source": "visitor"}, "source must be"),
        ({"unit": "9Z"}, "unit is not on the unit list"),
        ({"date": "01/10/2026"}, "date must be YYYY-MM-DD"),
        ({"date": "2999-01-01"}, "date is in the future"),
        ({"text": "x" * 5001}, "longer than"),
    ],
)
def test_bad_rows_are_reported_with_line_number(change, reason) -> None:
    rows, errors = parse_csv(make_csv([GOOD, {**GOOD, **change}]))
    assert len(rows) == 1
    assert len(errors) == 1
    assert errors[0].line == 3  # header is line 1
    assert reason in errors[0].reason


def test_errors_never_contain_the_comment() -> None:
    _, errors = parse_csv(make_csv([{**GOOD, "text": "Nurse Rose was rude", "unit": "nowhere"}]))
    assert "Rose" not in errors[0].reason


def test_accepts_byte_order_mark_and_any_column_order() -> None:
    data = "﻿unit,date,source,text\n4b,2026-10-01,Staff,Short staffed again\n".encode("utf-8")
    rows, errors = parse_csv(data)
    assert errors == []
    assert rows[0].unit == "4B"
    assert rows[0].source.value == "staff"


def test_missing_column_rejects_the_file() -> None:
    with pytest.raises(CsvFormatError, match="missing columns: unit"):
        parse_csv(make_csv([GOOD], header=("text", "source", "date")))


def test_thousand_row_file_loads(client) -> None:
    rows = []
    for i in range(1000):
        row = {**GOOD, "text": f"Comment {i}: Dr. Patel said discharge in {i % 7 + 1} days."}
        if i % 100 == 0:
            row["unit"] = "unknown"
        rows.append(row)
    response = client.post(
        "/imports",
        files={"file": ("october.csv", make_csv(rows), "text/csv")},
        headers=login(client, "analyst"),
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["saved"] == 990
    assert body["rejected"] == 10
    assert {e["reason"] for e in body["errors"]} == {"unit is not on the unit list"}

    listed = client.get("/comments", params={"limit": 1}, headers=login(client, "analyst")).json()
    assert listed["total"] == 990
    assert listed["comments"][0]["text"] == "Comment 1: Dr. <PERSON> said discharge in 2 days."
