"""Reads and checks feedback rows from a CSV upload or the web form (FR1).

CSV columns (header row required, any order, extra columns ignored):

    text     the comment
    source   patient, family, patient_family, staff, nurse or physician
    unit     a code from kaizen.units.UNITS, such as 4B
    date     YYYY-MM-DD

Error messages give the line number and the reason only, never the comment, so they are
safe to return and log.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

from kaizen.db import Source
from kaizen.units import is_known_unit

REQUIRED_COLUMNS = ("text", "source", "unit", "date")
MAX_TEXT_CHARS = 5000
MAX_ROWS = 20000

_SOURCES = {
    "patient": Source.PATIENT_FAMILY,
    "family": Source.PATIENT_FAMILY,
    "patient_family": Source.PATIENT_FAMILY,
    "patient/family": Source.PATIENT_FAMILY,
    "staff": Source.STAFF,
    "nurse": Source.STAFF,
    "physician": Source.STAFF,
}


@dataclass(frozen=True)
class FeedbackRow:
    text: str
    source: Source
    unit: str
    feedback_date: date


@dataclass(frozen=True)
class RowError:
    line: int
    reason: str


class CsvFormatError(ValueError):
    """The whole file is unusable (not UTF-8, missing columns, too many rows)."""


def check_row(text: str, source: str, unit: str, day: str) -> tuple[FeedbackRow | None, str | None]:
    text = (text or "").strip()
    if not text:
        return None, "text is empty"
    if len(text) > MAX_TEXT_CHARS:
        return None, f"text is longer than {MAX_TEXT_CHARS} characters"
    parsed_source = _SOURCES.get((source or "").strip().lower())
    if parsed_source is None:
        return None, "source must be patient, family, staff, nurse or physician"
    unit = (unit or "").strip().upper()
    if not is_known_unit(unit):
        return None, "unit is not on the unit list"
    try:
        parsed_date = date.fromisoformat((day or "").strip())
    except ValueError:
        return None, "date must be YYYY-MM-DD"
    if parsed_date > date.today():
        return None, "date is in the future"
    return FeedbackRow(text, parsed_source, unit, parsed_date), None


def parse_csv(data: bytes) -> tuple[list[FeedbackRow], list[RowError]]:
    try:
        content = data.decode("utf-8-sig")  # Excel adds a byte order mark
    except UnicodeDecodeError as exc:
        raise CsvFormatError("file is not UTF-8 text") from exc

    reader = csv.DictReader(io.StringIO(content, newline=""))
    columns = {c.strip().lower() for c in reader.fieldnames or []}
    missing = [c for c in REQUIRED_COLUMNS if c not in columns]
    if missing:
        raise CsvFormatError(f"missing columns: {', '.join(missing)}")

    rows: list[FeedbackRow] = []
    errors: list[RowError] = []
    for i, raw in enumerate(reader):
        if i >= MAX_ROWS:
            raise CsvFormatError(f"more than {MAX_ROWS} rows, split the file")
        line = reader.line_num
        if None in raw:
            errors.append(RowError(line, "row has more fields than the header"))
            continue
        values = {k.strip().lower(): v for k, v in raw.items() if k}
        row, reason = check_row(values.get("text"), values.get("source"), values.get("unit"), values.get("date"))
        if row is None:
            errors.append(RowError(line, reason))
        else:
            rows.append(row)
    return rows, errors
