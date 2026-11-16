"""Data integrity, leakage protection and evaluation orchestration."""
import csv
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

from kaizen.classify.labels import Labels
from kaizen.evaluation.generate import generate, TRANSPORT_WEEKS
from kaizen.evaluation.report import check, save
from kaizen.evaluation.ratings import score_issues
from kaizen.evaluation.run import csv_bytes, label_metrics, read_dataset
from kaizen.evaluation.score import agreement, human_labels, predictions
from kaizen.ingest.csv_import import parse_csv
from kaizen.issues.evaluate import planted_recovery

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def dataset():
    return generate()


def test_counts_schema_dates_and_ground_truth(dataset):
    rows, truth = dataset
    assert len(rows) == len(truth) == 2300
    assert len({r["text"] for r in rows}) == 2300
    assert Counter(t["source_group"] for t in truth) == {"patient_family": 1500, "staff": 800}
    parsed, errors = parse_csv(csv_bytes(rows))
    assert len(parsed) == 2300 and not errors
    assert all(set(r) == {"text", "source", "unit", "date"} for r in rows)
    assert len({t["planted"] for t in truth if t["planted"]}) == 8
    assert all(t["source_group"] == "patient_family" for t in truth if t["planted"] == "night_noise")
    assert {t["source_group"] for t in truth if t["planted"] == "discharge_medication"} == {"patient_family", "staff"}
    weekly = Counter(t["week"] for t in truth if t["planted"] == "transport")
    assert [weekly[i] for i in range(1, 7)] == TRANSPORT_WEEKS
    assert sum(t["planted"] is None for t in truth) == 800
    assert all(r["unit"] == "ED" for r, t in zip(rows, truth) if t["planted"] == "ed_wait")


def test_reproducible_scenario_split_and_checked_in_dataset(dataset):
    assert generate() == dataset
    rows, truth = dataset
    assert generate(1) != dataset
    assert read_dataset(ROOT / "data/synthetic") == dataset
    train = {t["scenario"] for t in truth if t["split"] == "train"}
    test = {t["scenario"] for t in truth if t["split"] == "test"}
    assert not train & test


def test_dataset_hash_mismatch_fails(tmp_path):
    import shutil
    for name in ("comments.csv", "truth.jsonl", "manifest.json"):
        shutil.copy(ROOT / "data/synthetic" / name, tmp_path / name)
    with (tmp_path / "comments.csv").open("a") as f:
        f.write("\n")
    with pytest.raises(ValueError, match="hashes"):
        read_dataset(tmp_path)


def test_missing_predictions_do_not_become_gold():
    label = Labels(sentiment="negative", categories=["safety"], stage="care_on_the_ward", urgency="high")
    result = label_metrics({1: label}, {})
    assert result["missing"] == 1
    assert result["stage_accuracy"] == 0
    assert result["targets"]["urgency_high_recall"]["status"] == "FAIL"
    assert label_metrics({}, {})["status"] == "NOT_MEASURED"


def test_absent_urgent_examples_are_not_a_pass():
    label = Labels(sentiment="positive", categories=[], stage="unclear", urgency="low")
    result = label_metrics({1: label}, {1: label})
    assert result["targets"]["urgency_high_recall"]["status"] == "NOT_MEASURED"


def test_recovery_keeps_unselected_rows_in_denominator():
    found = [SimpleNamespace(cluster=SimpleNamespace(members=[0, 1]))]
    truth = ["noise"] * 10
    assert planted_recovery(found, truth)["found"] == 0
    found[0].cluster.members.append(2)
    assert planted_recovery(found, truth)["found"] == 1


def test_no_fake_pass_for_missing_metrics(tmp_path):
    assert check(None, .8)["status"] == "NOT_MEASURED"
    assert check(.05, .05, operator="<")["status"] == "FAIL"
    save(tmp_path, {"metric": check(None, .8)})
    assert "NOT_MEASURED" in (tmp_path / "summary.md").read_text()
    assert json.loads((tmp_path / "results.json").read_text())["metric"]["value"] is None


def test_blank_annotations_and_duplicate_predictions_rejected(tmp_path):
    sheet = tmp_path / "sheet.csv"
    sheet.write_text("row_id,sentiment,categories,stage,urgency\n1,,,,\n")
    with pytest.raises(ValueError):
        human_labels(sheet)
    pred = tmp_path / "predictions.jsonl"
    pred.write_text('{"row_id": 1, "prediction": null}\n' * 2)
    with pytest.raises(ValueError, match="duplicate"):
        predictions(pred)


def test_issue_rubric_requires_both_raters_and_ten_comments(tmp_path):
    paths = [tmp_path / "one.csv", tmp_path / "two.csv"]
    fields = ["rank", "comment_id", "same_problem (y/n)", "name_is_specific (y/n)"]
    for path in paths:
        with path.open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for i in range(10):
                writer.writerow(dict(zip(fields, [1, i, "y" if i < 8 else "n", "y"])))
    assert score_issues(paths)["good_share"]["status"] == "PASS"
    paths[1].write_text(paths[1].read_text().replace("1,0,y,y", "1,0,n,y"))
    assert score_issues(paths)["good_share"]["status"] == "FAIL"
    with pytest.raises(ValueError, match="two"):
        score_issues(paths[:1])


def test_agreement_requires_matching_ids_and_handles_constant_labels():
    label = Labels(sentiment="positive", categories=[], stage="unclear", urgency="low")
    assert agreement({1: label}, {1: label})["sentiment"]["status"] == "NOT_MEASURED"
    with pytest.raises(ValueError, match="same comments"):
        agreement({1: label}, {2: label})


def test_real_csv_import_and_baseline_pipeline(client, app, dataset):
    from kaizen.classify.baseline import BaselineLabeller
    from kaizen.classify.run import label_comments
    from kaizen.evaluation.run import api_checks, comments, import_rows, inputs
    from tests.conftest import login

    rows, truth = dataset
    # Real de-identification on a small sample, not a gold-as-prediction fixture.
    chosen = list(range(24))
    headers = login(client, "analyst")
    assert import_rows(client, headers, [rows[i] for i in chosen])["saved"] == 24
    with app.state.sessionmaker() as session:
        saved = comments(session)
        model_inputs = inputs(saved)
        model = BaselineLabeller().fit(model_inputs[:12], [Labels.model_validate(truth[i]) for i in chosen[:12]])
        run = label_comments(session, model, workers=1)
        assert run.labelled == 24 and run.failed_batches == 0
        result = api_checks(client, headers, session, repeats=1)
        assert all(v["status"] == "PASS" for v in result["comparison_integrity"].values())
        assert all(v["http_200"]["status"] == "PASS" for v in result["endpoints"].values())


def test_public_labels_are_separate_and_raw_text_is_not_sent_to_model(tmp_path, monkeypatch):
    from kaizen.evaluation.public import evaluate_public
    calls = []
    monkeypatch.setattr("kaizen.evaluation.public.deidentify",
                        lambda raw: SimpleNamespace(text="cleaned feedback"))
    class Model:
        name = "test-double"
        def label(self, items):
            calls.extend(i.text for i in items)
            return {i.id: Labels(sentiment="positive", categories=[], stage="unclear", urgency="low") for i in items}
    path = tmp_path / "public.csv"
    path.write_text("text,fft_sentiment\nsynthetic raw example,1\nnot labelled,\n")
    result = evaluate_public(path, Model())
    assert calls == ["cleaned feedback"]
    assert result["comments_scored"] == 1
    assert result["unlabelled_excluded"] == 1
    assert "raw example" not in json.dumps(result)
    assert result["hcat_category_stage_urgency"]["status"] == "NOT_MEASURED"
