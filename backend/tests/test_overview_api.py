"""The overview, issue trend and comment filters (FR4, FR5), with the unit rule for managers (NFR1)."""

from __future__ import annotations

from datetime import date, timedelta

from kaizen.api.overview import weekly
from kaizen.db import Channel, Comment, CommentLabel, ImportBatch, LabelStatus, Source
from kaizen.issues.build import build_issues
from kaizen.issues.name import KeywordNamer
from tests.conftest import login
from tests.test_issues import FakeEmbedder, topic_texts

P, S = Source.PATIENT_FAMILY, Source.STAFF
AS_OF = date(2026, 10, 29)


def add(app, text, source, unit, day, categories=("environment",), stage="care_on_the_ward", labelled=True, confirmed=False):
    label = {"sentiment": "negative", "categories": list(categories), "stage": stage, "urgency": "low"}
    with app.state.sessionmaker() as session:
        batch = ImportBatch(channel=Channel.CSV)
        session.add(batch)
        session.flush()
        c = Comment(batch_id=batch.id, source=source, unit=unit, feedback_date=day, text=text)
        session.add(c)
        session.flush()
        if labelled:
            session.add(CommentLabel(
                comment_id=c.id, suggested=label, labeller="fake", prompt_version="x",
                status=LabelStatus.CONFIRMED if confirmed else LabelStatus.SUGGESTED, **label,
            ))
        session.commit()
        return c.id


def seed_issues(app):
    """Pharmacy comments on 4B, mostly in the last week so the issue is rising; noise on 3A."""
    texts, topics = topic_texts(10)
    for n, (text, topic) in enumerate(zip(texts, topics)):
        if topic == "pharmacy":
            day = AS_OF - timedelta(days=n % 5) if n % 10 < 7 else AS_OF - timedelta(days=20)
            add(app, text, P if n % 2 else S, "4B", day, confirmed=n % 10 == 0)
        elif topic == "noise":
            add(app, text, P, "3A", AS_OF - timedelta(days=40))
        else:
            add(app, text, S, "3A", AS_OF - timedelta(days=60))
    with app.state.sessionmaker() as session:
        build_issues(session, FakeEmbedder(), KeywordNamer(), min_cluster_size=5)


def test_weekly_blocks_end_on_as_of() -> None:
    weeks = weekly([(AS_OF, P), (AS_OF - timedelta(days=6), S), (AS_OF - timedelta(days=7), P), (AS_OF - timedelta(days=100), P)], AS_OF, 3)
    assert [w["end"] for w in weeks] == ["2026-10-15", "2026-10-22", "2026-10-29"]
    assert weeks[-1] == {"start": "2026-10-23", "end": "2026-10-29", "patient": 1, "staff": 1}
    assert weeks[-2]["patient"] == 1 and weeks[0]["patient"] == 0


def test_overview_before_any_run(app, client) -> None:
    add(app, "Too noisy", P, "4B", AS_OF, labelled=False)
    body = client.get("/overview", headers=login(client, "analyst")).json()
    assert body["comments"] == {"total": 1, "labelled": 0, "unlabelled": 1, "confirmed": 0, "patient": 1, "staff": 0, "new_since_run": 1}
    assert body["run"] is None
    assert body["issues"] == {"count": 0, "rising": 0, "top": []}
    assert len(body["weeks"]) == 12 and body["weeks"][-1]["patient"] == 1
    assert body["last_import"] is not None
    assert body["process"] is None


def test_overview_after_a_run(app, client) -> None:
    seed_issues(app)
    add(app, "Arrived after the run", P, "4B", AS_OF, labelled=False)
    body = client.get("/overview", headers=login(client, "analyst")).json()
    assert body["comments"]["total"] == 31
    assert body["comments"]["labelled"] == 30
    assert body["comments"]["unlabelled"] == 1
    assert body["comments"]["confirmed"] == 1
    assert body["comments"]["new_since_run"] == 1
    assert body["issues"]["count"] == 3
    assert body["issues"]["rising"] == 1
    top = body["issues"]["top"]
    assert [i["rank"] for i in top] == [1, 2, 3]
    assert set(top[0]) == {"id", "rank", "name", "size", "unit_size", "negative_share", "rising"}
    assert body["weeks_as_of"] == "2026-10-29"
    assert sum(w["patient"] + w["staff"] for w in body["weeks"]) == 31


def test_manager_overview_is_their_unit(app, client) -> None:
    seed_issues(app)
    body = client.get("/overview", headers=login(client, "manager4b")).json()
    assert body["unit"] == "4B"
    assert body["comments"]["total"] == 10
    assert body["issues"]["count"] == 1
    assert body["issues"]["top"][0]["unit_size"] == 10
    assert body["process"] is None


def test_trend_explains_rising(app, client) -> None:
    seed_issues(app)
    headers = login(client, "analyst")
    issues = client.get("/issues", headers=headers).json()["issues"]
    pharmacy = next(i for i in issues if any("pharmacy" in k for k in i["keywords"]))
    body = client.get(f"/issues/{pharmacy['id']}/trend", headers=headers).json()
    assert body["rising"] is True
    assert body["last_week"] == 7
    assert body["prior_weeks"] == 3
    assert body["prior_weekly_average"] == 0.75
    assert body["as_of"] == "2026-10-29"
    assert body["weeks"][-1]["end"] == "2026-10-29"
    assert sum(w["patient"] + w["staff"] for w in body["weeks"]) == 10
    assert client.get("/issues/9999/trend", headers=headers).status_code == 404


def test_manager_trend_is_scoped(app, client) -> None:
    seed_issues(app)
    issues = client.get("/issues", headers=login(client, "analyst")).json()["issues"]
    noise = next(i for i in issues if any("noise" in k for k in i["keywords"]))
    pharmacy = next(i for i in issues if any("pharmacy" in k for k in i["keywords"]))
    headers = login(client, "manager4b")
    assert client.get(f"/issues/{noise['id']}/trend", headers=headers).status_code == 404
    assert client.get(f"/issues/{pharmacy['id']}/trend", headers=headers).json()["unit"] == "4B"


def test_comment_filters(app, client) -> None:
    add(app, "a", P, "4B", AS_OF, categories=["communication", "safety"], stage="discharge_and_transfers")
    add(app, "b", S, "4B", AS_OF, categories=["safety"], confirmed=True)
    add(app, "c", P, "3A", AS_OF - timedelta(days=30), categories=["environment"])
    add(app, "d", P, "3A", AS_OF, labelled=False)
    headers = login(client, "analyst")

    def ids(**params):
        body = client.get("/comments", params=params, headers=headers).json()
        assert body["total"] == len(body["comments"])
        return [c["text"] for c in body["comments"]]

    assert ids() == ["a", "b", "c", "d"]
    assert ids(category="safety") == ["a", "b"]
    assert ids(category="safety", source="staff") == ["b"]
    assert ids(stage="discharge_and_transfers") == ["a"]
    assert ids(labelled="false") == ["d"]
    assert ids(labelled="true", unit="3a") == ["c"]
    assert ids(date_from="2026-10-15") == ["a", "b", "d"]
    body = client.get("/comments", params={"category": "safety"}, headers=headers).json()
    assert body["comments"][1]["labels"]["status"] == "confirmed"
    assert body["comments"][0]["labels"]["categories"] == ["communication", "safety"]
    assert client.get("/comments", headers=headers).json()["comments"][3]["labels"] is None
    assert client.get("/comments", params={"category": "colour"}, headers=headers).status_code == 422
    assert client.get("/comments", params={"stage": "lunch"}, headers=headers).status_code == 422
    bad = client.get("/comments", params={"date_from": "2026-11-02", "date_to": "2026-11-01"}, headers=headers)
    assert bad.status_code == 422

    manager = login(client, "manager4b")
    body = client.get("/comments", params={"category": "safety"}, headers=manager).json()
    assert body["total"] == 2
    assert client.get("/comments", params={"unit": "3A"}, headers=manager).status_code == 403


def test_compare_says_how_many_labels_are_checked(app, client) -> None:
    add(app, "a", P, "4B", AS_OF, confirmed=True)
    add(app, "b", S, "4B", AS_OF)
    add(app, "c", S, "4B", AS_OF, labelled=False)
    body = client.get("/compare", headers=login(client, "analyst")).json()
    assert body["totals"] == {"patient": 1, "staff": 1}
    assert body["checked"] == 1
