"""Processing new feedback from the app (FR3, FR4): POST /runs and GET /runs/latest."""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select

from kaizen.api.runs import Pipeline, default_pipeline
from kaizen.classify.labels import Category, Labels, Sentiment, Stage, Urgency
from kaizen.classify.synthetic import training_split
from kaizen.db import ActivityLog, Channel, Comment, CommentLabel, ImportBatch, Issue, ProcessRun, ProcessStatus, Source
from kaizen.issues.name import KeywordNamer
from tests.conftest import login
from tests.test_issues import FakeEmbedder, topic_texts


class FakeLabeller:
    name = "fake-labeller"
    version = "1"

    def label(self, items):
        return {
            i.id: Labels(sentiment=Sentiment.NEGATIVE, categories=[Category.ENVIRONMENT],
                         stage=Stage.CARE_ON_THE_WARD, urgency=Urgency.LOW)
            for i in items
        }


class BrokenLabeller(FakeLabeller):
    def label(self, items):
        raise RuntimeError("model not found")


def use(app, labeller) -> None:
    app.state.pipeline = Pipeline(lambda: labeller, FakeEmbedder, KeywordNamer)


def add_unlabelled(app, texts) -> None:
    with app.state.sessionmaker() as session:
        batch = ImportBatch(channel=Channel.CSV)
        session.add(batch)
        session.flush()
        session.add_all(
            Comment(batch_id=batch.id, source=Source.STAFF, unit="4B", feedback_date=date(2026, 10, 1), text=t)
            for t in texts
        )
        session.commit()


def wait(app) -> None:
    app.state.run_thread.join(timeout=30)
    assert not app.state.run_thread.is_alive()


def test_no_run_yet(client) -> None:
    assert client.get("/runs/latest", headers=login(client, "analyst")).json() == {"run": None}


def test_run_labels_and_builds_issues(app, client) -> None:
    texts, _ = topic_texts(10)
    add_unlabelled(app, texts)
    use(app, FakeLabeller())
    headers = login(client, "analyst")

    started = client.post("/runs", headers=headers)
    assert started.status_code == 202
    assert started.json()["status"] == "queued"
    assert started.json()["to_label"] == 30
    wait(app)

    run = client.get("/runs/latest", headers=headers).json()["run"]
    assert run["status"] == "done"
    assert run["labeller"] == "fake-labeller"
    assert run["labelled"] == 30
    assert run["issues"] == 3
    assert run["comments_used"] == 30
    assert run["started_at"] and run["finished_at"] and run["error"] is None

    with app.state.sessionmaker() as session:
        assert session.query(CommentLabel).count() == 30
        assert session.query(Issue).filter(Issue.run_id == run["issue_run_id"]).count() == 3
        actions = session.scalars(select(ActivityLog.action)).all()
    assert {"process_feedback", "label_comments", "build_issues", "process_feedback_done"} <= set(actions)

    # A second run has nothing to label but still rebuilds the issues.
    again = client.post("/runs", headers=headers)
    assert again.status_code == 202 and again.json()["to_label"] == 0
    wait(app)
    assert client.get("/runs/latest", headers=headers).json()["run"]["issue_run_id"] == run["issue_run_id"] + 1


def test_failed_run_reports_the_error(app, client) -> None:
    add_unlabelled(app, ["The ward was too noisy at night"])
    use(app, BrokenLabeller())
    headers = login(client, "admin")
    assert client.post("/runs", headers=headers).status_code == 202
    wait(app)
    run = client.get("/runs/latest", headers=headers).json()["run"]
    assert run["status"] == "failed"
    assert run["error"] == "RuntimeError: model not found"
    assert run["finished_at"]
    # The lock is free again, so the next run can start.
    assert not app.state.run_lock.locked()


def test_one_run_at_a_time(app, client) -> None:
    use(app, FakeLabeller())
    headers = login(client, "analyst")
    app.state.run_lock.acquire()
    try:
        response = client.post("/runs", headers=headers)
        assert response.status_code == 409
    finally:
        app.state.run_lock.release()


def test_run_left_by_a_stopped_server_is_marked_failed(app, client) -> None:
    with app.state.sessionmaker() as session:
        session.add(ProcessRun(status=ProcessStatus.RUNNING))
        session.commit()
    run = client.get("/runs/latest", headers=login(client, "analyst")).json()["run"]
    assert run["status"] == "failed"
    assert "server stopped" in run["error"]


def test_managers_cannot_run(client) -> None:
    headers = login(client, "manager4b")
    assert client.post("/runs", headers=headers).status_code == 403
    assert client.get("/runs/latest", headers=headers).status_code == 403
    assert client.post("/runs").status_code == 401


def test_default_labeller_depends_on_the_environment(monkeypatch) -> None:
    import kaizen.classify.synthetic as synthetic

    sentinel = object()
    monkeypatch.setattr(synthetic, "synthetic_baseline", lambda: sentinel)
    monkeypatch.delenv("KAIZEN_LABEL_MODEL", raising=False)
    assert default_pipeline().labeller() is sentinel

    monkeypatch.setenv("KAIZEN_LABEL_MODEL", "ollama/qwen2.5:7b")
    labeller = default_pipeline().labeller()
    assert type(labeller).__name__ == "LLMLabeller"


def test_training_split_uses_train_rows_only(tmp_path) -> None:
    (tmp_path / "comments.csv").write_text(
        "text,source,unit,date\n"
        "The pharmacy delayed my discharge,patient,4B,2026-10-01\n"
        "Nurses were lovely,patient,4B,2026-10-02\n"
        "Bed shortage again on nights,staff,ICU,2026-10-03\n",
        encoding="utf-8",
    )
    label = {"sentiment": "negative", "categories": ["institutional_processes"], "stage": "discharge_and_transfers", "urgency": "medium"}
    truth = [dict(label, split="train"), dict(label, sentiment="positive", categories=[], split="test"), dict(label, split="train")]
    (tmp_path / "truth.jsonl").write_text("\n".join(json.dumps(t) for t in truth) + "\n", encoding="utf-8")

    items, labels = training_split(tmp_path)
    assert [i.source for i in items] == ["patient_family", "staff"]
    assert [i.unit for i in items] == ["4B", "ICU"]
    assert all(lab.sentiment is Sentiment.NEGATIVE for lab in labels)
