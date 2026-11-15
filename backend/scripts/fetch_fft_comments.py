"""Downloads real NHS Friends and Family Test comments and converts them to our CSV upload format.

Source: `datasets/v6framework_230831.csv` in The-Strategy-Unit/pxtextmining (NHS England,
MIT licence), at a pinned commit and checked against its SHA-256, so the input never
changes under us. Two of the six NHS trusts in that project agreed to publish their
comments; the project's labellers gave each one a sentiment score from 1 (very positive) to
5 (very negative).

P3 scopes Kaizen to adult inpatient and emergency care. The closest part of this data is
North East Ambulance Service's "See and Convey" comments, from patients an ambulance crew
attended and took to hospital, so only those are kept and they are filed under unit `ED`.
The mental health, forensic, children's, NHS 111 and patient transport comments are left
out. The report has to say that these are ambulance comments, not ward comments.

The output is not committed: these are real patients' words, so they go through our
de-identification on upload like any other file, and the repo keeps only this script.

    python scripts/fetch_fft_comments.py                 # writes data/raw/fft-see-and-convey.csv
    python scripts/fetch_fft_comments.py --input local.csv

The output has the four upload columns plus `fft_comment_id` and `fft_sentiment`, which the
upload ignores but which let results be compared with the original labels later.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import sys
import urllib.request
from collections import Counter
from datetime import date, datetime
from pathlib import Path

COMMIT = "ba6c0a2f10ca9bb3b964b72afe6047b463095c75"
URL = f"https://raw.githubusercontent.com/The-Strategy-Unit/pxtextmining/{COMMIT}/datasets/v6framework_230831.csv"
SHA256 = "6c90cc740f2c486a17ef89be852f13f8ca434da4e2a06254a43288de7dc39567"
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "data" / "raw" / "fft-see-and-convey.csv"

TRUST = "NEAS"
SERVICE = "See and Convey"
UNIT = "ED"
OUT_COLUMNS = ["text", "source", "unit", "date", "fft_comment_id", "fft_sentiment"]


def parse_date(text: str) -> tuple[date, bool]:
    """The file mixes day/month/year (most rows, as a UK trust would write it) with
    month/day/year. Day first is tried first. Returns the date and whether it was ambiguous."""
    text = text.strip()
    day_first = month_first = None
    try:
        day_first = datetime.strptime(text, "%d/%m/%Y").date()
    except ValueError:
        pass
    try:
        month_first = datetime.strptime(text, "%m/%d/%Y").date()
    except ValueError:
        pass
    if day_first is None and month_first is None:
        raise ValueError(f"unreadable date {text!r}")
    ambiguous = day_first is not None and month_first is not None and day_first != month_first
    return (day_first or month_first), ambiguous


def convert(raw: str) -> tuple[list[dict], Counter]:
    counts: Counter = Counter()
    rows = []
    for row in csv.DictReader(io.StringIO(raw)):
        counts["rows"] += 1
        if row["Trust"].strip() != TRUST or row["Service type 1"].strip() != SERVICE:
            continue
        text = row["FFT answer"].strip()
        if not text:
            counts["empty"] += 1
            continue
        day, ambiguous = parse_date(row["Date"])
        counts["ambiguous_dates"] += ambiguous
        rows.append(
            {
                "text": text,
                "source": "patient",
                "unit": UNIT,
                "date": day.isoformat(),
                "fft_comment_id": row["Comment ID"].strip(),
                "fft_sentiment": row["Comment sentiment"].strip(),
            }
        )
    counts["kept"] = len(rows)
    return rows, counts


def download() -> str:
    with urllib.request.urlopen(URL, timeout=60) as response:
        data = response.read()
    digest = hashlib.sha256(data).hexdigest()
    if digest != SHA256:
        raise SystemExit(f"downloaded file has SHA-256 {digest}, expected {SHA256}; not using it")
    return data.decode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", type=Path, help="use a local copy instead of downloading")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    raw = args.input.read_text(encoding="utf-8") if args.input else download()
    rows, counts = convert(raw)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"{counts['kept']} comments written to {args.out} (from {counts['rows']} rows; "
        f"{counts['empty']} empty; {counts['ambiguous_dates']} dates could be read either way, read day first)",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
