"""Corrections by QI staff (FR6): each change is logged without comment text (NFR1)."""

from __future__ import annotations

import json
from datetime import date

from sqlalchemy import select

from kaizen.db import ActivityLog, Channel, Comment, CommentLabel, ImportBatch, Issue, IssueComment, Source, Suggestion
from kaizen.issues.build import build_issues
from kaizen.issues.name import KeywordNamer
from tests.conftest import login
from tests.test_issues import FakeEmbedder
from tests.test_issues_api import LABEL, by_keyword, setup_issues

TEXT = "The nurse <PERSON> told Mrs Okafor the wrong dose."


def add_comment(app, labelled=True) -> int:
    with app.state.sessionmaker() as session:
        batch = ImportBatch(channel=Channel.CSV)
        session.add(batch)
        session.flush()
        c = Comment(
            batch_id=batch.id,
            source=Source.STAFF,
            unit="4B",
            feedback_date=date(2026, 10, 1),
            text=TEXT,
            deid_counts={"PERSON": 1},
        )
        session.add(c)
        session.flush()
        if labelled:
            session.add(CommentLabel(comment_id=c.id, suggested=LABEL, labeller="fake", prompt_version="x", **LABEL))
        session.commit()
        return c.id


def log_rows(app) -> list[ActivityLog]:
    with app.state.sessionmaker() as session:
        return session.scalars(select(ActivityLog).order_by(ActivityLog.id)).all()


def last_logged(app, action: str) -> ActivityLog:
    return [row for row in log_rows(app) if row.action == action][-1]


def test_confirm_without_changes(app, client) -> None:
    cid = add_comment(app)
    body = client.post(f"/comments/{cid}/labels", json={}, headers=login(client, "analyst")).json()
    assert body["status"] == "confirmed" and body["confirmed_by"] is not None and body["confirmed_at"]
    assert body["urgency"] == "low" and body["suggested"] == LABEL
    last = log_rows(app)[-1]
    assert (last.action, last.entity_id, last.detail) == ("confirm_labels", cid, {"changed": []})


def test_correct_labels_keeps_suggested(app, client) -> None:
    cid = add_comment(app)
    headers = login(client, "analyst")
    response = client.post(
        f"/comments/{cid}/labels",
        json={"urgency": "high", "categories": ["safety", "communication", "safety"], "stage": "care_on_the_ward"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["urgency"] == "high" and body["categories"] == ["communication", "safety"]
    assert body["suggested"] == LABEL
    last = log_rows(app)[-1]
    # stage was sent but is the same as before, so it is not a change
    assert (last.action, last.detail) == ("correct_labels", {"changed": ["categories", "urgency"]})


def test_label_errors(app, client) -> None:
    cid = add_comment(app)
    unlabelled = add_comment(app, labelled=False)
    headers = login(client, "analyst")
    assert client.post(f"/comments/{cid}/labels", json={"urgency": "urgent"}, headers=headers).status_code == 422
    assert client.post(f"/comments/{cid}/labels", json={"categories": ["food"]}, headers=headers).status_code == 422
    assert client.post("/comments/9999/labels", json={}, headers=headers).status_code == 404
    assert client.post(f"/comments/{unlabelled}/labels", json={}, headers=headers).status_code == 409


def test_redact(app, client) -> None:
    cid = add_comment(app)
    start = TEXT.index("Mrs Okafor")
    end = start + len("Mrs Okafor")
    response = client.post(f"/comments/{cid}/redact", json={"start": start, "end": end}, headers=login(client, "analyst"))
    assert response.status_code == 200, response.text
    assert response.json()["text"] == "The nurse <PERSON> told <REDACTED> the wrong dose."
    with app.state.sessionmaker() as session:
        comment = session.get(Comment, cid)
        assert "Okafor" not in comment.text
        assert comment.deid_counts == {"PERSON": 1, "REDACTED": 1}
    last = log_rows(app)[-1]
    assert (last.action, last.entity_id, last.detail) == ("redact_comment", cid, {"length": 10})


def test_redact_bad_range(app, client) -> None:
    cid = add_comment(app)
    headers = login(client, "analyst")
    for bad in ({"start": 5, "end": 5}, {"start": 6, "end": 2}, {"start": 0, "end": len(TEXT) + 1}, {"start": -1, "end": 3}):
        assert client.post(f"/comments/{cid}/redact", json=bad, headers=headers).status_code == 422, bad
    assert client.post("/comments/9999/redact", json={"start": 0, "end": 1}, headers=headers).status_code == 404


def test_rename(app, client) -> None:
    setup_issues(app)
    headers = login(client, "analyst")
    issue = client.get("/issues", headers=headers).json()["issues"][0]
    response = client.post(f"/issues/{issue['id']}/rename", json={"name": "  Pharmacy delays at discharge "}, headers=headers)
    assert response.json()["name"] == "Pharmacy delays at discharge"
    assert client.get("/issues", headers=headers).json()["issues"][0]["name"] == "Pharmacy delays at discharge"
    for bad in ("", "   ", "x" * 121):
        assert client.post(f"/issues/{issue['id']}/rename", json={"name": bad}, headers=headers).status_code == 422
    assert client.post("/issues/9999/rename", json={"name": "x"}, headers=headers).status_code == 404
    assert last_logged(app, "rename_issue").detail == {"changed": ["name"]}


def test_merge(app, client) -> None:
    setup_issues(app)
    headers = login(client, "analyst")
    issues = client.get("/issues", headers=headers).json()["issues"]
    noise, triage = by_keyword(issues, "noise"), by_keyword(issues, "triage")
    with app.state.sessionmaker() as session:
        fields = {"issue_name": "x", "change": "x", "owner": "x", "stage": "unclear", "measure": "x"}
        session.add(Suggestion(issue_id=noise["id"], citations=[], drafted={}, model="fake", prompt_version="x", **fields))
        session.commit()

    response = client.post(f"/issues/{noise['id']}/merge", json={"into": triage["id"]}, headers=headers)
    assert response.status_code == 200, response.text
    merged = response.json()
    assert (merged["size"], merged["patient_count"], merged["staff_count"], merged["rank"]) == (20, 20, 0, 1)

    after = client.get("/issues", headers=headers).json()["issues"]
    assert [i["rank"] for i in after] == [1, 2] and noise["id"] not in {i["id"] for i in after}
    assert client.get(f"/issues/{triage['id']}/comments", headers=headers).json()["total"] == 20
    with app.state.sessionmaker() as session:
        assert session.get(Issue, noise["id"]) is None
        assert session.scalars(select(IssueComment).where(IssueComment.issue_id == noise["id"])).all() == []
        assert session.scalar(select(Suggestion.issue_id)) == triage["id"]
    last = last_logged(app, "merge_issue")
    assert (last.entity_id, last.detail) == (triage["id"], {"merged": noise["id"], "moved": 10})


def test_merge_errors(app, client) -> None:
    setup_issues(app)
    headers = login(client, "analyst")
    old = client.get("/issues", headers=headers).json()["issues"][0]
    assert client.post(f"/issues/{old['id']}/merge", json={"into": old["id"]}, headers=headers).status_code == 422
    assert client.post(f"/issues/{old['id']}/merge", json={"into": 9999}, headers=headers).status_code == 404
    with app.state.sessionmaker() as session:
        build_issues(session, FakeEmbedder(), KeywordNamer(), min_cluster_size=5)
    new = client.get("/issues", headers=headers).json()["issues"][0]
    assert client.post(f"/issues/{old['id']}/merge", json={"into": new["id"]}, headers=headers).status_code == 422


def test_only_qi_and_admin_can_correct(app, client) -> None:
    cid = add_comment(app)
    manager = login(client, "manager4b")
    assert client.post(f"/comments/{cid}/labels", json={}, headers=manager).status_code == 403
    assert client.post(f"/comments/{cid}/redact", json={"start": 0, "end": 1}, headers=manager).status_code == 403
    assert client.post("/issues/1/rename", json={"name": "x"}, headers=manager).status_code == 403
    assert client.post("/issues/1/merge", json={"into": 2}, headers=manager).status_code == 403
    assert client.post(f"/comments/{cid}/labels", json={}).status_code == 401
    assert client.post(f"/comments/{cid}/labels", json={}, headers=login(client, "admin")).status_code == 200


def test_log_never_holds_comment_text(app, client) -> None:
    cid = add_comment(app)
    headers = login(client, "analyst")
    client.post(f"/comments/{cid}/labels", json={"urgency": "high"}, headers=headers)
    client.post(f"/comments/{cid}/redact", json={"start": 0, "end": 3}, headers=headers)
    logged = json.dumps([row.detail for row in log_rows(app)])
    for word in ("nurse", "Okafor", "dose", "The"):
        assert word not in logged
