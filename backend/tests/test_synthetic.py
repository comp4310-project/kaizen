"""The synthetic data generator (scripts/make_synthetic.py) and the one-command evaluation (NFR5)."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pytest

from kaizen.classify.__main__ import load_labelled
from kaizen.classify.labels import Labels
from kaizen.ingest.csv_import import parse_csv
from kaizen.issues.rank import IssueComment, issue_stats
from tests.test_issues import FakeEmbedder

_spec = importlib.util.spec_from_file_location("make_synthetic", Path(__file__).parents[1] / "scripts" / "make_synthetic.py")
synth = importlib.util.module_from_spec(_spec)
sys.modules["make_synthetic"] = synth  # dataclasses look the module up while it loads
_spec.loader.exec_module(synth)

DATA = Path(__file__).parent / "data"


@pytest.fixture(scope="module")
def rows() -> list[dict]:
    return synth.generate()


def test_same_seed_same_files(tmp_path) -> None:
    a = synth.write(tmp_path / "a", seed=7, n=300, test_size=60)
    b = synth.write(tmp_path / "b", seed=7, n=300, test_size=60)
    c = synth.write(tmp_path / "c", seed=8, n=300, test_size=60)
    for name in a:
        assert a[name].read_bytes() == b[name].read_bytes(), name
    assert a["csv"].read_bytes() != c["csv"].read_bytes()


def test_committed_files_match_the_generator(tmp_path) -> None:
    fresh = synth.write(tmp_path)
    for path in fresh.values():
        # Git on Windows may check the committed copy out with CRLF line endings.
        committed = (DATA / path.name).read_bytes().replace(b"\r\n", b"\n")
        assert path.read_bytes() == committed, f"rerun scripts/make_synthetic.py, {path.name} is stale"


def test_size_sources_dates_and_background(rows) -> None:
    assert len(rows) == 1200
    sources = Counter(r["source"] for r in rows)
    assert 0.65 <= sources["patient_family"] / len(rows) <= 0.75
    background = sum(r["planted"] is None for r in rows) / len(rows)
    assert 0.35 <= background <= 0.45
    days = sorted({r["date"] for r in rows})
    assert (date.fromisoformat(days[-1]) - date.fromisoformat(days[0])).days == 83
    assert {r["unit"] for r in rows} == set(synth.ALL_UNITS)


def test_eight_problems_with_many_wordings(rows) -> None:
    by_problem = Counter(r["planted"] for r in rows if r["planted"])
    assert len(by_problem) == 8 and len({p.id for p in synth.PROBLEMS}) == 8
    assert by_problem.most_common(1)[0][0] == "discharge_meds_delay"  # the main test case
    for problem, n in by_problem.items():
        texts = {r["text"] for r in rows if r["planted"] == problem}
        assert len(texts) >= 0.8 * n, f"{problem} repeats itself"
        assert all(r["sentiment"] != "positive" for r in rows if r["planted"] == problem)


def test_staff_only_patient_only_and_rising(rows) -> None:
    def sources(problem: str) -> set[str]:
        return {r["source"] for r in rows if r["planted"] == problem}

    assert sources("handover_gaps") == {"staff"}
    assert sources("night_noise") == {"patient_family"}
    assert sources("discharge_meds_delay") == {"staff", "patient_family"}

    as_of = max(date.fromisoformat(r["date"]) for r in rows)
    rising = {}
    for p in synth.PROBLEMS:
        mine = [
            IssueComment(r["id"], r["source"], r["sentiment"], r["urgency"], r["stage"], tuple(r["categories"]), date.fromisoformat(r["date"]))
            for r in rows
            if r["planted"] == p.id
        ]
        rising[p.id] = issue_stats(mine, as_of).rising
    assert [p for p, flag in rising.items() if flag] == ["iv_pump_shortage"]


def test_labels_are_valid_and_some_are_urgent(rows) -> None:
    for r in rows:
        Labels.model_validate(r)
        if r["sentiment"] == "positive":
            assert r["categories"] == [] and r["urgency"] == "low"
    assert sum(r["urgency"] == "high" for r in rows) >= 60


def test_files_load_in_every_reader(tmp_path) -> None:
    paths = synth.write(tmp_path, seed=3, n=300, test_size=60)
    parsed, errors = parse_csv(paths["csv"].read_bytes())
    assert errors == [] and len(parsed) == 300
    assert [p.text for p in parsed] == [json.loads(line)["text"] for line in paths["all"].read_text(encoding="utf-8").splitlines()]

    train, _ = load_labelled(paths["train"])
    test, _ = load_labelled(paths["test"])
    assert len(test) == 60 and len(train) == 240
    assert not {i.id for i in train} & {i.id for i in test}


def test_evaluate_smoke(tmp_path) -> None:
    from kaizen.evaluate import run

    data = tmp_path / "data"
    synth.write(data, seed=5, n=300, test_size=60)
    out = tmp_path / "out"
    results = run(out, data, make_embedder=FakeEmbedder, timing_comments=40, extra_seeds=())

    ids = {c["id"] for c in results["checks"]}
    assert {"deid_recall", "baseline_sentiment_macro_f1", "issues_recovered", "fr5_staff_only", "fr4_rising_flagged", "nfr3_seconds"} <= ids
    assert results["details"]["issues"]["comments_imported"] == 300
    assert results["details"]["timing"]["comments"] == 40
    assert results["environment"]["libraries"]["scikit-learn"]
    saved = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert saved["checks"] == results["checks"]
    md = (out / "results.md").read_text(encoding="utf-8")
    assert "## Against the P3 targets" in md and "—" not in md
