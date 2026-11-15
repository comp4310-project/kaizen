"""The FFT converter (scripts/fetch_fft_comments.py). Uses a made-up file, so no download."""

from __future__ import annotations

import csv
import importlib.util
import io
from datetime import date
from pathlib import Path

import pytest

from kaizen.ingest.csv_import import parse_csv

_spec = importlib.util.spec_from_file_location("fetch_fft", Path(__file__).parents[1] / "scripts" / "fetch_fft_comments.py")
fetch = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(fetch)

HEADER = ["Comment ID", "Trust", "Respondent ID", "Date", "Service type 1", "Service type 2", "FFT answer", "Comment sentiment"]
ROWS = [
    ["1", "NEAS", "a", "30/09/2021", "See and Convey", "", "The crew were calm and kind.", "1"],
    ["2", "NEAS", "b", "1/14/2022", "See and Convey", "", "Waited three hours for the ambulance.", "5"],
    ["3", "NEAS", "c", "05/03/2022", "See and Convey", "", "Fine.", ""],
    ["4", "NEAS", "d", "05/03/2022", "See and Convey", "", "   ", "3"],
    ["5", "NEAS", "e", "05/03/2022", "111", "", "Call took ages.", "4"],
    ["6", "NHFT", "f", "05/03/2022", "Local partnerships- MH", "Adult mental health", "Good ward.", "1"],
]


def raw() -> str:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(HEADER)
    writer.writerows(ROWS)
    return out.getvalue()


def test_keeps_only_see_and_convey_comments_with_text() -> None:
    rows, counts = fetch.convert(raw())
    assert [r["fft_comment_id"] for r in rows] == ["1", "2", "3"]
    assert (counts["rows"], counts["kept"], counts["empty"]) == (6, 3, 1)
    assert all(r["unit"] == "ED" and r["source"] == "patient" for r in rows)
    assert [r["fft_sentiment"] for r in rows] == ["1", "5", ""]


def test_dates_are_read_day_first_unless_only_month_first_works() -> None:
    rows, counts = fetch.convert(raw())
    assert [r["date"] for r in rows] == ["2021-09-30", "2022-01-14", "2022-03-05"]
    assert counts["ambiguous_dates"] == 1  # 05/03/2022 could also be 3 May


def test_unreadable_date_is_an_error() -> None:
    with pytest.raises(ValueError, match="unreadable"):
        fetch.parse_date("2022-03-05")
    assert fetch.parse_date("13/01/2022") == (date(2022, 1, 13), False)


def test_output_passes_our_csv_upload_checks(tmp_path) -> None:
    rows, _ = fetch.convert(raw())
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=fetch.OUT_COLUMNS)
    writer.writeheader()
    writer.writerows(rows)
    parsed, errors = parse_csv(out.getvalue().encode("utf-8"))
    assert errors == [] and len(parsed) == 3
