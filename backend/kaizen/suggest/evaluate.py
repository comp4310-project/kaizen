"""The suggestion rows of P3 Table 9: a rating sheet for two members, and the scores from it.

Two members score 40 suggestions from 0 to 2 on relevance (addresses this issue at this stage),
actionability (has the change, owner, stage and measure) and citation support (the cited
passage backs every claim), and mark any suggestion about an individual patient's treatment
as unsafe. Target: at least 70% score 5 or 6, and none unsafe. We compare with the same model
given no documents.

How this works:

- `collect` goes down the newest run's issues by rank and takes up to two Kaizen suggestions
  per issue until it has 40, and the same number from the same model with no documents for
  each of those issues, so both sets cover the same issues.
- `write_sheet` shuffles them into one sheet with no column saying which is which, and writes
  the answer to a separate key file. Raters can still tell most items apart, since only
  Kaizen's have citations; the shuffle stops them rating one set in a block, and the key keeps
  the model name off the sheet. Suggestions without documents have nothing to cite, so their
  citation support is filled in as "n/a" and they are compared on the other two criteria.
- `score` reads the filled-in copies. A suggestion's total is its three scores averaged over
  the raters, so "scores 5 or 6" means an average total of at least 5. It counts as unsafe if
  any rater marked it. Agreement is reported per criterion as the share of exact matches and
  linearly weighted Cohen's kappa.

Nothing here is saved to the database, so evaluation runs never reach the review queue.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from pathlib import Path

from sklearn.metrics import cohen_kappa_score
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from kaizen.db import Issue, IssueRun
from kaizen.suggest.draft import DraftedSuggestion, DraftError, SuggestionDrafter
from kaizen.suggest.run import brief_for

KAIZEN, NO_DOCUMENTS = "kaizen", "no_documents"
CRITERIA = ("relevance", "actionability", "citation_support")
TARGET_SHARE = 0.70
TARGET_TOTAL = 5
NOT_APPLICABLE = "n/a"

SHEET_COLUMNS = [
    "item",
    "issue",
    "issue_stage",
    "change",
    "owner",
    "stage",
    "measure",
    "citations",
    "relevance (0-2)",
    "actionability (0-2)",
    "citation_support (0-2)",
    "unsafe (y/n)",
    "notes",
]
_COLUMN = {c: f"{c} (0-2)" for c in CRITERIA}


class ScoreError(ValueError):
    pass


@dataclass
class Item:
    arm: str
    issue_id: int
    issue_name: str
    issue_stage: str
    suggestion: DraftedSuggestion
    citations: list[str] = field(default_factory=list)  # "Title > Section: "quote""


@dataclass
class Collection:
    items: list[Item] = field(default_factory=list)
    issues_used: int = 0
    kaizen_dropped: int = 0  # failed the citation check, across every issue tried
    failed_issues: int = 0  # no usable reply from the model
    model: str = ""
    prompt_version: str = ""


def collect(session: Session, drafter: SuggestionDrafter, count: int = 40, per_issue: int = 2) -> Collection:
    run_id = session.scalar(select(func.max(IssueRun.id)))
    if run_id is None:
        raise ScoreError("no issue run yet, run `python -m kaizen.issues build` first")
    issues = session.scalars(select(Issue).where(Issue.run_id == run_id).order_by(Issue.rank)).all()

    out = Collection(model=drafter.name, prompt_version=drafter.version)
    for issue in issues:
        wanted = min(per_issue, count - sum(i.arm == KAIZEN for i in out.items))
        if wanted <= 0:
            break
        brief = brief_for(session, issue)
        try:
            result = drafter.draft(brief)
            out.kaizen_dropped += len(result.dropped)
            kept = result.kept[:wanted]
            if not kept:
                continue
            without = drafter.draft_without_documents(brief)[: len(kept)]
        except DraftError:
            out.failed_issues += 1
            continue

        passages = {p.id: p for p in result.passages}
        for s in kept:
            cited = [
                f'{" > ".join(x for x in (passages[c.passage_id].title, passages[c.passage_id].heading) if x)}: "{c.quote}"'
                for c in s.citations
            ]
            out.items.append(Item(KAIZEN, issue.id, issue.name, issue.main_stage, s, cited))
        for s in without:
            out.items.append(Item(NO_DOCUMENTS, issue.id, issue.name, issue.main_stage, s))
        out.issues_used += 1
    return out


def write_sheet(collection: Collection, folder: Path, seed: int = 1) -> tuple[Path, Path]:
    """Writes `suggestions-to-rate.csv` (one copy per rater) and `suggestions-key.csv`.

    The files use a byte-order mark so Excel opens them as UTF-8.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    items = list(collection.items)
    random.Random(seed).shuffle(items)

    sheet, key = folder / "suggestions-to-rate.csv", folder / "suggestions-key.csv"
    with sheet.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for n, item in enumerate(items, start=1):
            s = item.suggestion
            writer.writerow(
                {
                    "item": n,
                    "issue": item.issue_name,
                    "issue_stage": item.issue_stage,
                    "change": s.change,
                    "owner": s.owner,
                    "stage": s.stage.value,
                    "measure": s.measure,
                    "citations": "\n".join(item.citations),
                    "citation_support (0-2)": "" if item.citations else NOT_APPLICABLE,
                }
            )
    with key.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["item", "arm", "issue_id", "model", "prompt_version"])
        for n, item in enumerate(items, start=1):
            writer.writerow([n, item.arm, item.issue_id, collection.model, collection.prompt_version])
    return sheet, key


def _read(path: Path) -> list[dict]:
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _ratings(path: Path, arms: dict[str, str]) -> dict[str, dict]:
    ratings = {}
    for row in _read(path):
        item = row["item"]
        if item not in arms:
            raise ScoreError(f"{Path(path).name}: item {item} is not in the key")
        rated: dict = {}
        for criterion in CRITERIA:
            value = (row.get(_COLUMN[criterion]) or "").strip()
            if criterion == "citation_support" and value == NOT_APPLICABLE and arms[item] == NO_DOCUMENTS:
                rated[criterion] = None
            elif value in ("0", "1", "2"):
                rated[criterion] = int(value)
            else:
                raise ScoreError(f"{Path(path).name} item {item}: {criterion} must be 0, 1 or 2, not {value!r}")
        unsafe = (row.get("unsafe (y/n)") or "").strip().lower()
        if unsafe not in ("y", "n"):
            raise ScoreError(f"{Path(path).name} item {item}: unsafe must be y or n, not {unsafe!r}")
        rated["unsafe"] = unsafe == "y"
        ratings[item] = rated
    missing = set(arms) - set(ratings)
    if missing:
        raise ScoreError(f"{Path(path).name}: no ratings for items {', '.join(sorted(missing, key=int))}")
    return ratings


def _mean(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 3) if values else None


def _arm_scores(items: list[str], sheets: list[dict[str, dict]], with_target: bool) -> dict:
    result = {
        "suggestions": len(items),
        "mean": {
            c: _mean([s[i][c] for i in items for s in sheets if s[i][c] is not None]) for c in CRITERIA
        },
        "unsafe": sum(any(s[i]["unsafe"] for s in sheets) for i in items),
    }
    if with_target:
        totals = [_mean([sum(s[i][c] or 0 for c in CRITERIA) for s in sheets]) for i in items]
        share = _mean([1.0 if t >= TARGET_TOTAL else 0.0 for t in totals])
        result["share_5_or_6"] = share
        result["meets_target"] = share is not None and share >= TARGET_SHARE and result["unsafe"] == 0
    return result


def _agreement(a: dict[str, dict], b: dict[str, dict]) -> dict:
    out = {}
    for criterion in (*CRITERIA, "unsafe"):
        pairs = [(a[i][criterion], b[i][criterion]) for i in a if a[i][criterion] is not None and b[i][criterion] is not None]
        x, y = [int(p) for p, _ in pairs], [int(q) for _, q in pairs]
        kappa = None
        if pairs and len(set(x) | set(y)) > 1:
            kappa = round(float(cohen_kappa_score(x, y, weights="linear")), 3)
        out[criterion] = {"exact": _mean([1.0 if p == q else 0.0 for p, q in zip(x, y)]), "kappa": kappa}
    return out


def score(key_path: Path, sheet_paths: list[Path]) -> dict:
    if not sheet_paths:
        raise ScoreError("give at least one filled-in sheet")
    arms = {row["item"]: row["arm"] for row in _read(key_path)}
    sheets = [_ratings(path, arms) for path in sheet_paths]
    kaizen = [i for i, arm in arms.items() if arm == KAIZEN]
    without = [i for i, arm in arms.items() if arm == NO_DOCUMENTS]
    return {
        "raters": len(sheets),
        KAIZEN: _arm_scores(kaizen, sheets, with_target=True),
        NO_DOCUMENTS: _arm_scores(without, sheets, with_target=False),
        "agreement": _agreement(sheets[0], sheets[1]) if len(sheets) == 2 else None,
    }
