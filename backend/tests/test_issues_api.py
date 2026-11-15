"""Issue endpoints for the dashboard (FR4, FR8), including the unit rule for managers (NFR1)."""

from __future__ import annotations

import csv
import io
from datetime import date

from sqlalchemy import select

from kaizen.db import ActivityLog, Channel, Comment, CommentLabel, ImportBatch, IssueComment, Source
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


def csv_rows(response) -> list[dict]:
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("text/csv")
    return list(csv.DictReader(io.StringIO(response.text)))


def as_csv(comment: dict) -> dict:
    labels = comment["labels"]
    return {
        "id": str(comment["id"]),
        "source": comment["source"],
        "unit": comment["unit"],
        "date": comment["date"],
        "typical": "yes" if comment["typical"] else "no",
        "sentiment": labels["sentiment"],
        "categories": ";".join(labels["categories"]),
        "stage": labels["stage"],
        "urgency": labels["urgency"],
        "status": labels["status"],
        "text": comment["text"],
    }


def test_csv_export_matches_the_json_view(client, app) -> None:
    setup_issues(app)
    for username in ("analyst", "manager4b"):
        headers = login(client, username)
        noise = by_keyword(client.get("/issues", headers=headers).json()["issues"], "noise")
        url = f"/issues/{noise['id']}/comments"
        for params in ({}, {"limit": 3, "offset": 2}, {"source": "patient_family"}, {"source": "staff"}):
            view = client.get(url, params=params, headers=headers).json()
            exported = csv_rows(client.get(url, params={**params, "format": "csv"}, headers=headers))
            assert exported == [as_csv(c) for c in view["comments"]], (username, params)
        assert len(exported) == 0  # the last filter is staff, and every test comment is from a patient


def test_csv_export_unit_filter_and_rules(app, client) -> None:
    setup_issues(app)
    headers = login(client, "analyst")
    noise = by_keyword(client.get("/issues", headers=headers).json()["issues"], "noise")
    url = f"/issues/{noise['id']}/comments"
    rows = csv_rows(client.get(url, params={"unit": "3a", "format": "csv"}, headers=headers))
    assert len(rows) == 6 and {r["unit"] for r in rows} == {"3A"}

    manager = login(client, "manager4b")
    assert client.get(url, params={"unit": "3A", "format": "csv"}, headers=manager).status_code == 403
    assert client.get(url, params={"format": "xlsx"}, headers=headers).status_code == 422
    with app.state.sessionmaker() as session:
        assert "export_issue_comments" in session.scalars(select(ActivityLog.action)).all()


def test_csv_cells_that_look_like_formulas_are_quoted(app, client) -> None:
    setup_issues(app)
    with app.state.sessionmaker() as session:
        link = session.scalars(select(IssueComment)).first()
        session.get(Comment, link.comment_id).text = '=HYPERLINK("http://example.test")'
        session.commit()
    response = client.get(f"/issues/{link.issue_id}/comments", params={"format": "csv"}, headers=login(client, "analyst"))
    texts = [r["text"] for r in csv_rows(response)]
    assert "'=HYPERLINK(\"http://example.test\")" in texts


def test_issues_need_login(client) -> None:
    assert client.get("/issues").status_code == 401
    assert client.get("/issues/1/comments").status_code == 401
