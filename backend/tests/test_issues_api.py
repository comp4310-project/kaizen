"""Issue endpoints for the dashboard (FR4, FR8), including the unit rule for managers (NFR1)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from kaizen.db import ActivityLog, Channel, Comment, CommentLabel, ImportBatch, Source
from kaizen.issues.build import build_issues
from kaizen.issues.name import KeywordNamer
from tests.conftest import login
from tests.test_issues import FakeEmbedder, topic_texts

LABEL = {"sentiment": "negative", "categories": ["environment"], "stage": "care_on_the_ward", "urgency": "low"}


def add(app, texts, unit):
    with app.state.sessionmaker() as session:
        batch = ImportBatch(channel=Channel.CSV)
        session.add(batch)
        session.flush()
        for text in texts:
            c = Comment(batch_id=batch.id, source=Source.PATIENT_FAMILY, unit=unit, feedback_date=date(2026, 10, 1), text=text)
            session.add(c)
            session.flush()
            session.add(CommentLabel(comment_id=c.id, suggested=LABEL, labeller="fake", prompt_version="x", **LABEL))
        session.commit()


def setup_issues(app):
    texts, topics = topic_texts(10)
    # pharmacy comments on 4B, noise split across 4B and 3A, triage only on 3A
    add(app, [t for t, p in zip(texts, topics) if p == "pharmacy"], "4B")
    noise = [t for t, p in zip(texts, topics) if p == "noise"]
    add(app, noise[:4], "4B")
    add(app, noise[4:], "3A")
    add(app, [t for t, p in zip(texts, topics) if p == "triage"], "3A")
    with app.state.sessionmaker() as session:
        build_issues(session, FakeEmbedder(), KeywordNamer(), min_cluster_size=5)


def by_keyword(issues, word):
    return next(i for i in issues if any(word in k for k in i["keywords"]))


def test_no_run_yet(client) -> None:
    response = client.get("/issues", headers=login(client, "analyst"))
    assert response.json() == {"run": None, "issues": []}


def test_analyst_sees_every_issue_and_its_comments(app, client) -> None:
    setup_issues(app)
    headers = login(client, "analyst")
    body = client.get("/issues", headers=headers).json()
    assert body["run"]["comments_used"] == 30
    assert [i["rank"] for i in body["issues"]] == [1, 2, 3]
    assert all(i["unit_size"] is None for i in body["issues"])

    triage = by_keyword(body["issues"], "triage")
    detail = client.get(f"/issues/{triage['id']}/comments", headers=headers).json()
    assert detail["total"] == 10
    assert detail["comments"][0]["typical"] is True
    assert detail["comments"][0]["labels"] == {**LABEL, "status": "suggested"}

    with app.state.sessionmaker() as session:
        actions = session.scalars(select(ActivityLog.action)).all()
    assert "view_issues" in actions and "view_issue_comments" in actions


def test_manager_sees_only_their_unit(app, client) -> None:
    setup_issues(app)
    headers = login(client, "manager4b")
    issues = client.get("/issues", headers=headers).json()["issues"]

    assert len(issues) == 2  # triage has no 4B comments
    noise = by_keyword(issues, "noise")
    assert (noise["size"], noise["unit_size"]) == (10, 4)
    comments = client.get(f"/issues/{noise['id']}/comments", headers=headers).json()
    assert comments["total"] == 4 and {c["unit"] for c in comments["comments"]} == {"4B"}

    analyst = client.get("/issues", headers=login(client, "analyst")).json()["issues"]
    triage = by_keyword(analyst, "triage")
    assert client.get(f"/issues/{triage['id']}/comments", headers=headers).status_code == 404
    assert client.get("/issues/9999/comments", headers=headers).status_code == 404


def test_issues_need_login(client) -> None:
    assert client.get("/issues").status_code == 401
    assert client.get("/issues/1/comments").status_code == 401
