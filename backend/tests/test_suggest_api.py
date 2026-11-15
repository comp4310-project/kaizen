"""Suggestion endpoints: draft for an issue, list them, and accept, edit or reject (FR7, NFR2)."""

from __future__ import annotations

from sqlalchemy import select

from kaizen.db import ActivityLog, Suggestion
from kaizen.suggest.draft import SuggestionDrafter
from kaizen.suggest.retrieve import PassageIndex
from tests.conftest import login
from tests.test_issues_api import setup_issues
from tests.test_suggest_draft import GOOD, PASSAGES, FakeCompletion, reply
from tests.test_suggest_retrieve import FakeEmbedder


def use_drafter(app, completion=None, passages=PASSAGES) -> FakeCompletion:
    completion = completion or FakeCompletion([GOOD, {**GOOD, "citations": []}])
    app.state.drafter = SuggestionDrafter(PassageIndex.build(passages, FakeEmbedder()), completion=completion, model="fake/model")
    return completion


def first_issue(client, headers) -> dict:
    return client.get("/issues", headers=headers).json()["issues"][0]


def draft(client, headers, issue_id):
    return client.post(f"/issues/{issue_id}/suggestions", headers=headers)


def test_drafting_saves_only_supported_suggestions(app, client) -> None:
    setup_issues(app)
    use_drafter(app)
    headers = login(client, "analyst")
    issue = first_issue(client, headers)

    response = draft(client, headers, issue["id"])
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["dropped"] == 1 and body["reasons"] == ["no citation"]
    (s,) = body["suggestions"]
    assert s["status"] == "suggested"
    assert s["issue"] == {"id": issue["id"], "name": issue["name"]}
    assert s["citations"][0]["quote"] == GOOD["citations"][0]["quote"]

    listed = client.get(f"/issues/{issue['id']}/suggestions", headers=headers).json()
    assert [x["id"] for x in listed["suggestions"]] == [s["id"]]


def test_unknown_issue_is_404(app, client) -> None:
    use_drafter(app)
    assert draft(client, login(client, "analyst"), 9999).status_code == 404


def test_no_documents_is_503_not_an_empty_answer(app, client) -> None:
    setup_issues(app)
    completion = use_drafter(app, passages=[])
    headers = login(client, "analyst")
    response = draft(client, headers, first_issue(client, headers)["id"])
    assert response.status_code == 503
    assert completion.calls == []


def test_unusable_model_reply_is_502_and_saves_nothing(app, client) -> None:
    setup_issues(app)
    use_drafter(app, FakeCompletion(respond=lambda _: reply("{not json")))
    headers = login(client, "analyst")
    assert draft(client, headers, first_issue(client, headers)["id"]).status_code == 502
    with app.state.sessionmaker() as session:
        assert session.scalars(select(Suggestion)).all() == []


def test_managers_cannot_draft_or_review(app, client) -> None:
    setup_issues(app)
    use_drafter(app)
    analyst = login(client, "analyst")
    issue_id = first_issue(client, analyst)["id"]
    s = draft(client, analyst, issue_id).json()["suggestions"][0]

    manager = login(client, "manager4b")
    assert draft(client, manager, issue_id).status_code == 403
    assert client.get("/suggestions", headers=manager).status_code == 403
    assert client.post(f"/suggestions/{s['id']}/decision", headers=manager, json={"decision": "accept"}).status_code == 403


def decide(client, headers, suggestion_id, **body):
    return client.post(f"/suggestions/{suggestion_id}/decision", headers=headers, json=body)


def drafted(app, client) -> tuple[dict, dict]:
    setup_issues(app)
    use_drafter(app)
    headers = login(client, "analyst")
    return headers, draft(client, headers, first_issue(client, headers)["id"]).json()["suggestions"][0]


def test_accept_and_reject_record_who_decided(app, client) -> None:
    headers, s = drafted(app, client)
    accepted = decide(client, headers, s["id"], decision="accept").json()
    assert accepted["status"] == "accepted" and accepted["decided_by"] == "analyst"
    assert accepted["decided_at"] is not None

    # A person can change their mind; each decision is logged.
    assert decide(client, headers, s["id"], decision="reject").json()["status"] == "rejected"
    with app.state.sessionmaker() as session:
        details = session.scalars(select(ActivityLog.detail).where(ActivityLog.action == "decide_suggestion")).all()
    assert [d["decision"] for d in details] == ["accept", "reject"]


def test_edit_changes_the_text_but_keeps_what_the_model_wrote(app, client) -> None:
    headers, s = drafted(app, client)
    edited = decide(client, headers, s["id"], decision="edit", owner="Discharge planning team").json()
    assert edited["status"] == "edited"
    assert edited["owner"] == "Discharge planning team"
    assert edited["change"] == GOOD["change"]

    with app.state.sessionmaker() as session:
        row = session.get(Suggestion, s["id"])
        assert row.drafted["owner"] == GOOD["owner"]
        log = session.scalars(select(ActivityLog).where(ActivityLog.action == "decide_suggestion")).one()
    # Field names only, never the text (NFR1).
    assert log.detail == {"decision": "edit", "edited": ["owner"]}


def test_bad_decisions_are_rejected(app, client) -> None:
    headers, s = drafted(app, client)
    assert decide(client, headers, s["id"], decision="maybe").status_code == 422
    assert decide(client, headers, s["id"], decision="edit").status_code == 422  # nothing to change
    assert decide(client, headers, s["id"], decision="edit", owner="   ").status_code == 422
    assert decide(client, headers, s["id"], decision="edit", stage="lunch").status_code == 422
    assert decide(client, headers, s["id"], decision="accept", owner="Someone").status_code == 422  # edits need "edit"
    assert decide(client, headers, 9999, decision="accept").status_code == 404


def test_review_queue_lists_undecided_suggestions(app, client) -> None:
    headers, s = drafted(app, client)
    queue = client.get("/suggestions", headers=headers, params={"status": "suggested"}).json()
    assert [x["id"] for x in queue["suggestions"]] == [s["id"]]
    decide(client, headers, s["id"], decision="accept")
    assert client.get("/suggestions", headers=headers, params={"status": "suggested"}).json()["suggestions"] == []
    assert len(client.get("/suggestions", headers=headers).json()["suggestions"]) == 1


def test_suggestions_need_login(client) -> None:
    assert client.get("/suggestions").status_code == 401
    assert client.post("/issues/1/suggestions").status_code == 401
