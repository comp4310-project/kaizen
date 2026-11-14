"""Drafting cited suggestions for an issue (FR7) and dropping unsupported ones (NFR2).

LiteLLM is replaced by a fake completion function and the embedder by a fake, so these run
offline.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from kaizen.db import ActivityLog, Suggestion, SuggestionStatus
from kaizen.suggest.corpus import Passage
from kaizen.suggest.draft import DraftError, IssueBrief, SuggestionDrafter, save_suggestions
from kaizen.suggest.retrieve import PassageIndex
from tests.test_suggest_retrieve import FakeEmbedder

MODEL = "anthropic/claude-opus-5-5"

PASSAGES = [
    Passage(
        "meds-policy:0",
        "meds-policy",
        "Discharge medication reconciliation",
        "Procedure > Before discharge",
        "The pharmacist checks the home medication list against the discharge prescription "
        "and sends it to the community pharmacy the day before discharge.",
    ),
    Passage("noise-qs:0", "noise-qs", "Quiet at night", "", "Wards keep noise at night low so patients can sleep."),
]

BRIEF = IssueBrief(
    issue_id=12,
    name="Discharge medications delayed by pharmacy",
    keywords=("discharge", "pharmacy", "prescription"),
    main_stage="discharge_and_transfers",
    comment_ids=(4, 9, 15),
)

GOOD = {
    "change": "Send discharge prescriptions to pharmacy the day before planned discharge.",
    "owner": "Inpatient pharmacy lead",
    "stage": "discharge_and_transfers",
    "measure": "Share of discharges where medications are ready at the planned time.",
    "citations": [
        {"passage_id": "meds-policy:0", "quote": "sends it to the community pharmacy the day before discharge"}
    ],
}


def reply(text: str | None, finish_reason: str = "stop"):
    return SimpleNamespace(choices=[SimpleNamespace(finish_reason=finish_reason, message=SimpleNamespace(content=text))])


class FakeCompletion:
    def __init__(self, suggestions=None, respond=None):
        self.calls = []
        self._respond = respond or (lambda _: reply(json.dumps({"suggestions": suggestions or []})))

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        return self._respond(kwargs)


def drafter(fake, passages=PASSAGES) -> SuggestionDrafter:
    return SuggestionDrafter(PassageIndex.build(passages, FakeEmbedder()), completion=fake, model=MODEL)


def test_request_sends_issue_and_passages_with_a_schema_limited_to_those_passages() -> None:
    fake = FakeCompletion([GOOD])
    drafter(fake).draft(BRIEF)

    call = fake.calls[0]
    assert call["model"] == MODEL
    assert call["reasoning_effort"] == "medium"
    assert call["messages"][0]["role"] == "system"
    assert call["messages"][0]["content"][0]["cache_control"] == {"type": "ephemeral"}
    sent = json.loads(call["messages"][1]["content"])
    assert sent["issue"]["name"] == BRIEF.name
    assert [p["id"] for p in sent["passages"]] == ["meds-policy:0", "noise-qs:0"]
    citation = call["response_format"]["json_schema"]["schema"]["properties"]["suggestions"]["items"]["properties"]["citations"]
    assert citation["items"]["properties"]["passage_id"]["enum"] == ["meds-policy:0", "noise-qs:0"]
    # Comment ids are kept for the record but are never part of the request.
    assert "comment_ids" not in json.dumps(sent)


def test_supported_suggestion_is_kept() -> None:
    result = drafter(FakeCompletion([GOOD])).draft(BRIEF)
    assert result.dropped == []
    (kept,) = result.kept
    assert kept.change == GOOD["change"]
    assert kept.citations[0].passage_id == "meds-policy:0"


@pytest.mark.parametrize(
    "change, reason",
    [
        ({"citations": [{"passage_id": "meds-policy:0", "quote": "sends it to the hospital pharmacy the day before discharge"}]}, "quote not found in meds-policy:0"),
        ({"citations": []}, "no citation"),
        ({"citations": [{"passage_id": "made-up:3", "quote": "sends it to the community pharmacy the day before discharge"}]}, "cites a passage it was not given"),
        ({"owner": "  "}, "missing owner"),
    ],
)
def test_unsupported_suggestions_are_dropped_with_a_reason(change, reason) -> None:
    result = drafter(FakeCompletion([GOOD, {**GOOD, **change}])).draft(BRIEF)
    assert len(result.kept) == 1
    assert [r for _, r in result.dropped] == [reason]


def test_one_bad_quote_drops_the_whole_suggestion() -> None:
    two = {**GOOD, "citations": GOOD["citations"] + [{"passage_id": "noise-qs:0", "quote": "wards keep noise at night very low"}]}
    result = drafter(FakeCompletion([two])).draft(BRIEF)
    assert result.kept == [] and len(result.dropped) == 1


def test_at_most_three_are_kept() -> None:
    result = drafter(FakeCompletion([GOOD] * 5)).draft(BRIEF)
    assert len(result.kept) == 3


def test_no_documents_means_no_request() -> None:
    fake = FakeCompletion([GOOD])
    result = drafter(fake, passages=[]).draft(BRIEF)
    assert result.kept == [] and result.passages == [] and fake.calls == []


@pytest.mark.parametrize(
    "respond",
    [
        lambda _: reply('{"suggestions": [{"change": 1'),
        lambda _: reply(None),
        lambda _: reply("{}", finish_reason="length"),
    ],
)
def test_unusable_replies_raise_draft_error(respond) -> None:
    with pytest.raises(DraftError):
        drafter(FakeCompletion(respond=respond)).draft(BRIEF)


def test_saved_suggestions_keep_a_copy_of_the_issue(app) -> None:
    d = drafter(FakeCompletion([GOOD, {**GOOD, "citations": []}]))
    result = d.draft(BRIEF)
    with app.state.sessionmaker() as session:
        saved = save_suggestions(session, BRIEF, result, d, user_id=None)
        assert len(saved) == 1

        row = session.scalars(select(Suggestion)).one()
        assert (row.issue_id, row.issue_name) == (12, BRIEF.name)
        assert row.issue_keywords == list(BRIEF.keywords)
        assert row.issue_comment_ids == [4, 9, 15]
        assert row.status is SuggestionStatus.SUGGESTED
        assert row.owner == GOOD["owner"]
        assert row.citations == [
            {
                "passage_id": "meds-policy:0",
                "document_id": "meds-policy",
                "title": "Discharge medication reconciliation",
                "heading": "Procedure > Before discharge",
                "quote": GOOD["citations"][0]["quote"],
            }
        ]
        assert row.drafted["change"] == GOOD["change"]  # kept unchanged when a person edits it
        assert row.model == f"{MODEL}/medium"

        log = session.scalars(select(ActivityLog).where(ActivityLog.action == "draft_suggestions")).one()
        assert (log.entity_type, log.entity_id) == ("issue", 12)
        assert log.detail == {"kept": 1, "dropped": 1, "reasons": ["no citation"], "model": f"{MODEL}/medium", "prompt_version": d.version}


def test_litellm_sends_claude_the_schema_effort_and_cached_prompt(monkeypatch) -> None:
    """Runs the real LiteLLM translation; the request goes to a closed local port, not Anthropic."""
    import litellm

    from tests.test_classify import _Spy

    fake = FakeCompletion([GOOD])
    drafter(fake).draft(BRIEF)
    spy = _Spy()
    monkeypatch.setattr(litellm, "callbacks", [spy])
    with pytest.raises(Exception):
        litellm.completion(api_key="test", api_base="http://127.0.0.1:9", timeout=5, **{**fake.calls[0], "num_retries": 0})

    body = spy.body
    assert body["model"] == "claude-opus-5-5"
    assert body["output_format"]["schema"]["properties"]["suggestions"]["items"]["properties"]["citations"]["items"][
        "properties"
    ]["passage_id"]["enum"] == ["meds-policy:0", "noise-qs:0"]
    assert body["output_config"] == {"effort": "medium"}
    assert body["system"][0]["cache_control"] == {"type": "ephemeral"}
