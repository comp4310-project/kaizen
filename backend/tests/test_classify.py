"""Labelling (FR3). LiteLLM is replaced by a fake completion function, so these run without an API key."""

from __future__ import annotations

import json
from datetime import date
from types import SimpleNamespace

import kaizen.classify  # noqa: F401  (must load before litellm, see its __init__)
import litellm
import pytest
from litellm.integrations.custom_logger import CustomLogger
from sqlalchemy import select

from kaizen.classify.__main__ import load_labelled
from kaizen.classify.baseline import BaselineLabeller
from kaizen.classify.labels import Category, Labels, Sentiment, Stage, Urgency
from kaizen.classify.llm import LabelError, LLMLabeller
from kaizen.classify.metrics import score
from kaizen.classify.prompt import BATCH_SCHEMA, CommentInput
from kaizen.classify.run import label_comments
from kaizen.db import ActivityLog, Channel, Comment, CommentLabel, ImportBatch, LabelStatus, Source
from tests.conftest import login
from tests.test_import import make_csv
from tests.test_privacy import CANARIES

LABEL = {"sentiment": "negative", "categories": ["communication"], "stage": "discharge_and_transfers", "urgency": "medium"}
MODEL = "anthropic/claude-haiku-5-5"


def reply(text: str | None, finish_reason: str = "stop"):
    """The parts of a LiteLLM response the labeller reads."""
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason, message=SimpleNamespace(content=text))])


def echo(kwargs):
    """Labels every comment in the request the same way."""
    ids = [c["id"] for c in json.loads(kwargs["messages"][1]["content"])]
    return reply(json.dumps({"labels": [{"id": i, **LABEL} for i in ids]}))


class FakeCompletion:
    """Stands in for litellm.completion and keeps every request."""

    def __init__(self, respond=echo):
        self.calls = []
        self._respond = respond

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self._respond(kwargs)


def raises(exc):
    def respond(_):
        raise exc

    return respond


ITEMS = [
    CommentInput(1, "Nobody told us what the scan showed before we went home.", "patient_family", "4B"),
    CommentInput(2, "<PERSON> on nights handed over without the falls risk.", "staff", "3A"),
]


def test_request_uses_cached_prompt_schema_and_low_effort() -> None:
    fake = FakeCompletion()
    result = LLMLabeller(completion=fake, model=MODEL).label(ITEMS)

    assert set(result) == {1, 2}
    assert result[1] == Labels.model_validate(LABEL)
    call = fake.calls[0]
    assert call["model"] == MODEL
    assert call["reasoning_effort"] == "low"
    assert call["response_format"]["json_schema"]["schema"] == BATCH_SCHEMA
    assert call["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    assert call["num_retries"] > 0
    # Sampling parameters are rejected by current Claude models.
    assert not {"temperature", "top_p", "top_k"} & set(call)
    sent = json.loads(call["messages"][1]["content"])
    assert [c["text"] for c in sent] == [i.text for i in ITEMS]


class _Spy(CustomLogger):
    def __init__(self):
        super().__init__()
        self.body = None

    def log_pre_api_call(self, model, messages, kwargs):
        self.body = kwargs["additional_args"]["complete_input_dict"]


def test_litellm_sends_claude_the_schema_effort_and_cached_prompt(monkeypatch) -> None:
    """Runs the real LiteLLM translation; the request goes to a closed local port, not Anthropic."""
    fake = FakeCompletion()
    LLMLabeller(completion=fake, model=MODEL).label(ITEMS)
    spy = _Spy()
    monkeypatch.setattr(litellm, "callbacks", [spy])
    request = {**fake.calls[0], "num_retries": 0}
    with pytest.raises(Exception):
        litellm.completion(api_key="test", api_base="http://127.0.0.1:9", timeout=5, **request)

    body = spy.body
    assert body["model"] == "claude-haiku-5-5"
    assert body["output_format"] == {"type": "json_schema", "schema": BATCH_SCHEMA}
    assert body["output_config"] == {"effort": "low"}
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert not {"temperature", "top_p", "top_k"} & set(body)


def test_schema_lists_every_label() -> None:
    item = BATCH_SCHEMA["properties"]["labels"]["items"]["properties"]
    assert item["sentiment"]["enum"] == [s.value for s in Sentiment]
    assert item["categories"]["items"]["enum"] == [c.value for c in Category]
    assert item["stage"]["enum"] == [s.value for s in Stage]
    assert item["urgency"]["enum"] == [u.value for u in Urgency]


@pytest.mark.parametrize(
    "respond",
    [
        lambda _: reply("", finish_reason="content_filter"),
        lambda _: reply('{"labels": [', finish_reason="length"),
        lambda _: reply('{"labels": [{"id": 1, "sentiment": "angry"}]}'),
        lambda _: reply(None),
        raises(litellm.RateLimitError("slow down", "anthropic", MODEL)),
        raises(litellm.APIConnectionError("no route", "anthropic", MODEL)),
    ],
)
def test_unusable_replies_fail_the_batch(respond) -> None:
    with pytest.raises(LabelError):
        LLMLabeller(completion=FakeCompletion(respond)).label(ITEMS)


def test_a_bad_key_stops_the_run() -> None:
    with pytest.raises(litellm.AuthenticationError):
        LLMLabeller(completion=FakeCompletion(raises(litellm.AuthenticationError("bad key", "anthropic", MODEL)))).label(ITEMS)


def test_ids_not_asked_for_are_dropped_and_repeats_removed() -> None:
    labels = [{"id": 1, **LABEL, "categories": ["safety", "safety"]}, {"id": 99, **LABEL}]
    result = LLMLabeller(completion=FakeCompletion(lambda _: reply(json.dumps({"labels": labels})))).label(ITEMS)
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
    fake = FakeCompletion()
    labeller = LLMLabeller(completion=fake, model=MODEL)

    with app.state.sessionmaker() as session:
        run = label_comments(session, labeller, batch_size=10, workers=2)
        assert (run.labelled, run.missed, run.failed_batches) == (23, 0, 0)
        assert len(fake.calls) == 3

        rows = session.scalars(select(CommentLabel)).all()
        assert sorted(r.comment_id for r in rows) == ids
        row = rows[0]
        assert row.status is LabelStatus.SUGGESTED
        assert row.suggested == {**LABEL, "categories": ["communication"]}
        assert row.labeller == f"{MODEL}/low"
        assert row.prompt_version == labeller.version

        # Second run: nothing left to label, so no more API calls.
        again = label_comments(session, labeller)
        assert again.labelled == 0
        assert len(fake.calls) == 3
        log = session.scalars(select(ActivityLog).where(ActivityLog.action == "label_comments")).all()
        assert log[0].detail["labelled"] == 23


def test_failed_batches_are_left_for_the_next_run(app) -> None:
    add_comments(app, [f"Comment {n}" for n in range(4)])
    calls = {"n": 0}

    def flaky(kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return reply("", finish_reason="content_filter")
        return echo(kwargs)

    labeller = LLMLabeller(completion=FakeCompletion(flaky))
    with app.state.sessionmaker() as session:
        first = label_comments(session, labeller, batch_size=2, workers=1)
        assert (first.labelled, first.failed_batches) == (2, 1)
        second = label_comments(session, labeller, batch_size=2, workers=1)
        assert second.labelled == 2
        assert len(session.scalars(select(CommentLabel)).all()) == 4


def test_llm_never_sees_original_text(app, client) -> None:
    """The NFR1 canary check from test_privacy, applied to what is sent to the LLM."""
    text = "My dad was seen by " + ", ".join(CANARIES.values()) + "."
    rows = [{"text": text, "source": "family", "unit": "4B", "date": "2026-10-02"}]
    response = client.post("/imports", files={"file": ("f.csv", make_csv(rows))}, headers=login(client, "analyst"))
    assert response.status_code == 201, response.text

    fake = FakeCompletion()
    with app.state.sessionmaker() as session:
        assert label_comments(session, LLMLabeller(completion=fake)).labelled == 1

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
