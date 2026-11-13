"""Labelling (FR3). Claude is replaced by a fake client, so these run without an API key."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from kaizen.classify.__main__ import load_labelled
from kaizen.classify.baseline import BaselineLabeller
from kaizen.classify.claude import ClaudeLabeller, LabelError
from kaizen.classify.labels import Category, Labels, Sentiment, Stage, Urgency
from kaizen.classify.metrics import score
from kaizen.classify.prompt import BATCH_SCHEMA, CommentInput
from kaizen.classify.run import label_comments
from kaizen.db import ActivityLog, Channel, Comment, CommentLabel, ImportBatch, LabelStatus, Source
from tests.conftest import login
from tests.test_import import make_csv
from tests.test_privacy import CANARIES

LABEL = {"sentiment": "negative", "categories": ["communication"], "stage": "discharge_and_transfers", "urgency": "medium"}


def reply(text: str, stop_reason: str = "end_turn"):
    # Thinking comes first on current models, so the labeller has to look for the text block.
    return SimpleNamespace(
        stop_reason=stop_reason,
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
    )


def echo(kwargs):
    """Labels every comment in the request the same way."""
    ids = [c["id"] for c in json.loads(kwargs["messages"][0]["content"])]
    return reply(json.dumps({"labels": [{"id": i, **LABEL} for i in ids]}))


class FakeClient:
    def __init__(self, respond=echo):
        self.calls = []
        self.messages = self
        self._respond = respond

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._respond(kwargs)


ITEMS = [
    CommentInput(1, "Nobody told us what the scan showed before we went home.", "patient_family", "4B"),
    CommentInput(2, "<PERSON> on nights handed over without the falls risk.", "staff", "3A"),
]


def test_request_uses_cached_prompt_schema_and_low_effort() -> None:
    client = FakeClient()
    result = ClaudeLabeller(client=client, model="claude-haiku-5-5").label(ITEMS)

    assert set(result) == {1, 2}
    assert result[1] == Labels.model_validate(LABEL)
    call = client.calls[0]
    assert call["model"] == "claude-haiku-5-5"
    assert call["output_config"] == {"format": {"type": "json_schema", "schema": BATCH_SCHEMA}, "effort": "low"}
    assert call["system"][0]["cache_control"] == {"type": "ephemeral"}
    # Sampling parameters are rejected by current models.
    assert not {"temperature", "top_p", "top_k"} & set(call)
    sent = json.loads(call["messages"][0]["content"])
    assert [c["text"] for c in sent] == [i.text for i in ITEMS]


def test_schema_lists_every_label() -> None:
    item = BATCH_SCHEMA["properties"]["labels"]["items"]["properties"]
    assert item["sentiment"]["enum"] == [s.value for s in Sentiment]
    assert item["categories"]["items"]["enum"] == [c.value for c in Category]
    assert item["stage"]["enum"] == [s.value for s in Stage]
    assert item["urgency"]["enum"] == [u.value for u in Urgency]


@pytest.mark.parametrize(
    "response",
    [
        reply("", stop_reason="refusal"),
        reply('{"labels": [', stop_reason="max_tokens"),
        reply('{"labels": [{"id": 1, "sentiment": "angry"}]}'),
        SimpleNamespace(stop_reason="end_turn", content=[]),
    ],
)
def test_unusable_replies_fail_the_batch(response) -> None:
    with pytest.raises(LabelError):
        ClaudeLabeller(client=FakeClient(lambda _: response)).label(ITEMS)


def test_ids_not_asked_for_are_dropped_and_repeats_removed() -> None:
    labels = [{"id": 1, **LABEL, "categories": ["safety", "safety"]}, {"id": 99, **LABEL}]
    result = ClaudeLabeller(client=FakeClient(lambda _: reply(json.dumps({"labels": labels})))).label(ITEMS)
    assert set(result) == {1}
    assert result[1].categories == [Category.SAFETY]


def add_comments(app, texts: list[str]) -> list[int]:
    with app.state.sessionmaker() as session:
        batch = ImportBatch(channel=Channel.CSV)
        session.add(batch)
        session.flush()
        comments = [
            Comment(batch_id=batch.id, source=Source.PATIENT_FAMILY, unit="4B", feedback_date=date(2026, 10, 1), text=t)
            for t in texts
        ]
        session.add_all(comments)
        session.commit()
        return [c.id for c in comments]


def test_run_labels_new_comments_once(app) -> None:
    ids = add_comments(app, [f"Comment {n} about discharge." for n in range(23)])
    client = FakeClient()
    labeller = ClaudeLabeller(client=client, model="claude-haiku-5-5")

    with app.state.sessionmaker() as session:
        run = label_comments(session, labeller, batch_size=10, workers=2)
        assert (run.labelled, run.missed, run.failed_batches) == (23, 0, 0)
        assert len(client.calls) == 3

        rows = session.scalars(select(CommentLabel)).all()
        assert sorted(r.comment_id for r in rows) == ids
        row = rows[0]
        assert row.status is LabelStatus.SUGGESTED
        assert row.suggested == {**LABEL, "categories": ["communication"]}
        assert row.labeller == "claude-haiku-5-5/low"
        assert row.prompt_version == labeller.version

        # Second run: nothing left to label, so no more API calls.
        again = label_comments(session, labeller)
        assert again.labelled == 0
        assert len(client.calls) == 3
        log = session.scalars(select(ActivityLog).where(ActivityLog.action == "label_comments")).all()
        assert log[0].detail["labelled"] == 23


def test_failed_batches_are_left_for_the_next_run(app) -> None:
    add_comments(app, [f"Comment {n}" for n in range(4)])
    calls = {"n": 0}

    def flaky(kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return reply("", stop_reason="refusal")
        return echo(kwargs)

    labeller = ClaudeLabeller(client=FakeClient(flaky))
    with app.state.sessionmaker() as session:
        first = label_comments(session, labeller, batch_size=2, workers=1)
        assert (first.labelled, first.failed_batches) == (2, 1)
        second = label_comments(session, labeller, batch_size=2, workers=1)
        assert second.labelled == 2
        assert len(session.scalars(select(CommentLabel)).all()) == 4


def test_llm_never_sees_original_text(app, client) -> None:
    """The NFR1 canary check from test_privacy, applied to what is sent to Claude."""
    text = "My dad was seen by " + ", ".join(CANARIES.values()) + "."
    rows = [{"text": text, "source": "family", "unit": "4B", "date": "2026-10-02"}]
    response = client.post("/imports", files={"file": ("f.csv", make_csv(rows))}, headers=login(client, "analyst"))
    assert response.status_code == 201, response.text

    fake = FakeClient()
    with app.state.sessionmaker() as session:
        assert label_comments(session, ClaudeLabeller(client=fake)).labelled == 1

    sent = json.dumps(fake.calls, default=str)
    for canary in CANARIES:
        assert canary not in sent, canary


def test_scores_count_skipped_comments_as_wrong() -> None:
    gold = {1: Labels.model_validate(LABEL), 2: Labels.model_validate({**LABEL, "urgency": "high", "stage": "admissions"})}
    perfect = score(gold, dict(gold))
    assert perfect["sentiment_macro_f1"] == pytest.approx(1 / 3)  # only one of three sentiments appears
    assert perfect["category_micro_f1"] == 1.0
    assert perfect["stage_accuracy"] == 1.0
    assert perfect["urgency_high_recall"] == 1.0
    assert perfect["missing"] == 0

    half = score(gold, {1: gold[1]})
    assert half["missing"] == 1
    assert half["stage_accuracy"] == 0.5
    assert half["urgency_high_recall"] == 0.0
    assert half["meets_target"]["urgency_high_recall"] is False


def test_baseline_learns_from_labelled_examples() -> None:
    texts = {
        "positive": ["Lovely nurses, thank you", "Great care, very kind staff", "Thank you to the whole team"],
        "negative": ["Waited hours with no update", "Nobody explained my discharge", "Rude nurse ignored my pain"],
    }
    items, labels = [], []
    for sentiment, examples in texts.items():
        for text in examples:
            items.append(CommentInput(len(items) + 1, text, "patient_family", "4B"))
            labels.append(
                Labels(
                    sentiment=Sentiment(sentiment),
                    categories=[] if sentiment == "positive" else [Category.COMMUNICATION],
                    stage=Stage.CARE_ON_THE_WARD,
                    urgency=Urgency.LOW,
                )
            )
    model = BaselineLabeller().fit(items, labels)
    predicted = model.label(items)

    assert set(predicted) == {i.id for i in items}
    assert all(p.stage is Stage.CARE_ON_THE_WARD for p in predicted.values())  # only stage seen in training
    assert all(Category.SAFETY not in p.categories for p in predicted.values())  # never seen in training
    assert sum(predicted[i.id].sentiment == lab.sentiment for i, lab in zip(items, labels)) >= 5


def test_load_labelled_file(tmp_path) -> None:
    path = tmp_path / "gold.jsonl"
    path.write_text(
        json.dumps({"id": 7, "text": "Cold food.", "source": "patient_family", "unit": "4B", **LABEL}) + "\n\n",
        encoding="utf-8",
    )
    items, labels = load_labelled(path)
    assert items == [CommentInput(7, "Cold food.", "patient_family", "4B")]
    assert labels[7].stage is Stage.DISCHARGE_AND_TRANSFERS


def test_config_error_stops_the_run_without_sending_the_rest(app) -> None:
    """A wrong key or model name fails every batch, so the queued ones should not be sent."""
    add_comments(app, [f"Comment {n}" for n in range(20)])

    class BadKey:
        name, version = "fake/bad-key", "x"

        def __init__(self) -> None:
            self.calls = 0

        def label(self, items):
            self.calls += 1
            raise PermissionError("invalid api key")

    labeller = BadKey()
    with app.state.sessionmaker() as session:
        with pytest.raises(PermissionError):
            label_comments(session, labeller, batch_size=2, workers=1)
    # One worker may pick up a second batch before the first error is seen, never all ten.
    assert labeller.calls <= 2
