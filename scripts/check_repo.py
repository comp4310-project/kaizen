#!/usr/bin/env python3
"""Checks the repo for things we don't want committed.

No dependencies, so it runs the same in CI and locally:

    python3 scripts/check_repo.py

Looks for secret files, oversized files, student IDs, and broken relative links.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

MAX_FILE_BYTES = 5 * 1024 * 1024

SECRET_PATTERNS = (
    re.compile(r"(^|/)\.env$"),
    re.compile(r"(^|/)\.env\.(?!example$)"),
    re.compile(r"\.pem$"),
    re.compile(r"(^|/)credentials\.json$"),
    re.compile(r"(^|/)secrets\.json$"),
)

LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")

# Lakehead student IDs are 7 digits. The repo is public, so they must not appear in it.
STUDENT_ID = re.compile(r"(?<!\d)\d{7}(?!\d)")
ID_SUFFIXES = {".md", ".txt", ".yml", ".yaml"}


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [Path(p) for p in out.split("\0") if p]


def check_secrets(files: list[Path]) -> list[str]:
    problems = []
    for path in files:
        posix = path.as_posix()
        if any(pattern.search(posix) for pattern in SECRET_PATTERNS):
            problems.append(f"{posix}: secret file, should not be committed")
    return problems


def check_sizes(files: list[Path]) -> list[str]:
    problems = []
    for path in files:
        if not path.is_file():
            continue
        size = path.stat().st_size
        if size > MAX_FILE_BYTES:
            mb = size / 1024 / 1024
            problems.append(f"{path.as_posix()}: {mb:.1f} MB, over the {MAX_FILE_BYTES // 1024 // 1024} MB limit")
    return problems


def check_student_ids(files: list[Path]) -> list[str]:
    problems = []
    for path in files:
        if path.suffix.lower() not in ID_SUFFIXES or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            if STUDENT_ID.search(line):
                problems.append(
                    f"{path.as_posix()}:{line_no}: 7-digit number, looks like a student ID. "
                    "This repo is public, keep IDs in the D2L submission only."
                )
    return problems


def check_links(files: list[Path]) -> list[str]:
    problems = []
    for path in files:
        if path.suffix.lower() != ".md" or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for target in LINK.findall(text):
            target = target.split()[0].strip()
            if target.startswith(("http://", "https://", "mailto:", "#", "<")):
                continue
            resolved = (path.parent / target.split("#")[0]).resolve()
            if not resolved.exists():
                problems.append(f"{path.as_posix()}: broken relative link -> {target}")
    return problems


def main() -> int:
    files = tracked_files()
    problems: list[str] = []
    problems += check_secrets(files)
    problems += check_sizes(files)
    problems += check_student_ids(files)
    problems += check_links(files)

    if problems:
        print(f"{len(problems)} problem(s):\n")
        for problem in problems:
            print(f"  FAIL  {problem}")
        return 1

    print(f"OK - checked {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
