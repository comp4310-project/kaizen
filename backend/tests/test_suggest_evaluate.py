"""The suggestion rating sheet and its scores (P3 Table 9). Fake LLM and embedder, so offline."""

from __future__ import annotations

import csv
import json

import pytest

from kaizen.suggest.draft import SuggestionDrafter
from kaizen.suggest.evaluate import ScoreError, collect, score, write_sheet
from kaizen.suggest.retrieve import PassageIndex
from tests.test_issues_api import setup_issues
from tests.test_suggest_draft import GOOD, PASSAGES, reply
from tests.test_suggest_retrieve import FakeEmbedder

SECOND = {**GOOD, "change": "Pharmacy confirms the take-home prescription by noon on discharge day.", "owner": "Pharmacy manager"}
NO_DOCS = {k: v for k, v in GOOD.items() if k != "citations"}


class TwoArms:
    """Answers the cited request with Kaizen suggestions and the no-documents one without."""

    def __init__(self, cited=(GOOD, SECOND), fail_first=False) -> None:
        self.cited = list(cited)
        self.fail_first = fail_first
        self.calls = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail_first and len(self.calls) == 1:
            return reply("{not json")
        content = json.loads(kwargs["messages"][1]["content"])
        if "passages" in content:
            return reply(json.dumps({"suggestions": self.cited}))
        return reply(json.dumps({"suggestions": [NO_DOCS] * 3}))


def drafter(completion) -> SuggestionDrafter:
    return SuggestionDrafter(PassageIndex.build(PASSAGES, FakeEmbedder()), completion=completion, model="fake/model")


def collected(app, completion=None, count=4):
    setup_issues(app)
    with app.state.sessionmaker() as session:
        return collect(session, drafter(completion or TwoArms()), count=count, per_issue=2)


def test_collect_matches_each_issue_with_the_same_number_without_documents(app) -> None:
    c = collected(app)
    arms = [item.arm for item in c.items]
    assert arms.count("kaizen") == 4 and arms.count("no_documents") == 4
    assert c.issues_used == 2  # two per issue, so the third issue isn't needed
    for issue_id in {item.issue_id for item in c.items}:
        mine = [item.arm for item in c.items if item.issue_id == issue_id]
        assert mine.count("kaizen") == mine.count("no_documents") == 2


def test_issues_where_everything_was_dropped_are_skipped_but_counted(app) -> None:
    c = collected(app, TwoArms(cited=[{**GOOD, "citations": []}]))
    assert c.items == []
    assert c.kaizen_dropped == 3  # one per issue, all three issues tried


def test_a_failed_issue_is_skipped(app) -> None:
    c = collected(app, TwoArms(fail_first=True))
    assert c.failed_issues == 1
    assert [item.arm for item in c.items].count("kaizen") == 4


def test_no_issue_run_is_an_error(app) -> None:
    with app.state.sessionmaker() as session, pytest.raises(ScoreError, match="issues build"):
        collect(session, drafter(TwoArms()))


def read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def test_sheet_hides_which_arm_each_item_came_from(app, tmp_path) -> None:
    sheet, key = write_sheet(collected(app), tmp_path, seed=3)
    rows, keys = read(sheet), read(key)

    assert len(rows) == len(keys) == 8
    assert not any("kaizen" in json.dumps(r) or "no_documents" in json.dumps(r) for r in rows)
    assert [r["item"] for r in rows] == [str(n) for n in range(1, 9)]
    assert {k["arm"] for k in keys} == {"kaizen", "no_documents"}

    by_item = {k["item"]: k["arm"] for k in keys}
    for r in rows:
        if by_item[r["item"]] == "kaizen":
            assert "Discharge medication reconciliation > Procedure > Before discharge" in r["citations"]
            assert r["citation_support (0-2)"] == ""
        else:
            assert r["citations"] == ""
            assert r["citation_support (0-2)"] == "n/a"  # nothing to judge

    # Same seed, same order, so both raters' copies line up.
    sheet2, _ = write_sheet(collected(app), tmp_path / "again", seed=3)
    assert [r["change"] for r in read(sheet2)] == [r["change"] for r in rows]


def fill(sheet, path, ratings):
    """ratings: arm -> (relevance, actionability, citation_support, unsafe)."""
    rows = read(sheet)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        for r in rows:
            rel, act, cit, unsafe = ratings(r)
            r["relevance (0-2)"], r["actionability (0-2)"], r["unsafe (y/n)"] = rel, act, unsafe
            if r["citation_support (0-2)"] != "n/a":
                r["citation_support (0-2)"] = cit
            writer.writerow(r)
    return path


def test_score_reports_each_arm_against_the_targets(app, tmp_path) -> None:
    sheet, key = write_sheet(collected(app), tmp_path, seed=3)
    arm = {k["item"]: k["arm"] for k in read(key)}
    kaizen_items = sorted((i for i, a in arm.items() if a == "kaizen"), key=int)

    def rater_a(r):
        if arm[r["item"]] == "kaizen":
            # three of four Kaizen items score 6, one scores 3
            return ("1", "1", "1", "n") if r["item"] == kaizen_items[0] else ("2", "2", "2", "n")
        return ("1", "2", "", "n")

    def rater_b(r):
        rel, act, cit, unsafe = rater_a(r)
        if arm[r["item"]] == "no_documents" and r["item"] == min((i for i in arm if arm[i] == "no_documents"), key=int):
            unsafe = "y"
        return rel, act, cit, unsafe

    result = score(key, [fill(sheet, tmp_path / "a.csv", rater_a), fill(sheet, tmp_path / "b.csv", rater_b)])

    k = result["kaizen"]
    assert k["suggestions"] == 4
    assert k["share_5_or_6"] == 0.75
    assert k["unsafe"] == 0
    assert k["meets_target"] is True
    assert k["mean"] == {"relevance": 1.75, "actionability": 1.75, "citation_support": 1.75}

    n = result["no_documents"]
    assert n["mean"] == {"relevance": 1.0, "actionability": 2.0, "citation_support": None}
    assert n["unsafe"] == 1  # one rater is enough
    assert "meets_target" not in n

    assert result["agreement"]["relevance"]["exact"] == 1.0
    assert result["agreement"]["unsafe"]["exact"] == 7 / 8


def test_one_sheet_scores_without_agreement(app, tmp_path) -> None:
    sheet, key = write_sheet(collected(app), tmp_path)
    result = score(key, [fill(sheet, tmp_path / "a.csv", lambda r: ("2", "2", "2", "n"))])
    assert result["agreement"] is None
    assert result["kaizen"]["share_5_or_6"] == 1.0


@pytest.mark.parametrize("bad", ["3", "", "two"])
def test_bad_ratings_name_the_sheet_and_item(app, tmp_path, bad) -> None:
    sheet, key = write_sheet(collected(app), tmp_path)
    filled = fill(sheet, tmp_path / "a.csv", lambda r: (bad if r["item"] == "5" else "2", "2", "2", "n"))
    with pytest.raises(ScoreError, match=r"a\.csv item 5: relevance"):
        score(key, [filled])


def test_unsafe_must_be_y_or_n(app, tmp_path) -> None:
    sheet, key = write_sheet(collected(app), tmp_path)
    filled = fill(sheet, tmp_path / "a.csv", lambda r: ("2", "2", "2", "maybe"))
    with pytest.raises(ScoreError, match="unsafe"):
        score(key, [filled])


def test_kaizen_items_need_a_citation_score(app, tmp_path) -> None:
    sheet, key = write_sheet(collected(app), tmp_path)
    kaizen = next(k["item"] for k in read(key) if k["arm"] == "kaizen")
    filled = fill(sheet, tmp_path / "a.csv", lambda r: ("2", "2", "n/a" if r["item"] == kaizen else "2", "n"))
    with pytest.raises(ScoreError, match=f"item {kaizen}: citation_support"):
        score(key, [filled])
