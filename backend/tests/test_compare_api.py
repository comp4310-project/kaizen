"""The patient and staff comparison (FR5), including the unit rule for managers (NFR1)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select

from kaizen.db import ActivityLog, Channel, Comment, CommentLabel, ImportBatch, Source
from tests.conftest import login


def add(app, source, unit, day, stage, categories):
    label = {"sentiment": "negative", "categories": categories, "stage": stage, "urgency": "low"}
    with app.state.sessionmaker() as session:
        batch = ImportBatch(channel=Channel.CSV)
        session.add(batch)
        session.flush()
        c = Comment(batch_id=batch.id, source=source, unit=unit, feedback_date=day, text="synthetic comment")
        session.add(c)
        session.flush()
        session.add(CommentLabel(comment_id=c.id, suggested=label, labeller="fake", prompt_version="x", **label))
        session.commit()


P, S = Source.PATIENT_FAMILY, Source.STAFF
OCT = date(2026, 10, 1)
NOV = date(2026, 11, 1)


def seed(app):
    # Communication: both groups. Safety: staff only. Environment: patients only, all on 3A.
    add(app, P, "4B", OCT, "discharge_and_transfers", ["communication"])
    add(app, P, "4B", NOV, "discharge_and_transfers", ["communication", "safety"])
    add(app, S, "4B", OCT, "care_on_the_ward", ["communication", "safety"])
    add(app, S, "4B", NOV, "care_on_the_ward", ["safety"])
    add(app, P, "3A", OCT, "care_on_the_ward", ["environment"])
    add(app, P, "3A", OCT, "care_on_the_ward", [])


def rows(body):
    return {r["key"]: (r["patient"], r["staff"], r["only"]) for r in body["rows"]}


def test_by_category_marks_one_sided_rows(app, client) -> None:
    seed(app)
    body = client.get("/compare", headers=login(client, "analyst")).json()
    assert body["by"] == "category"
    assert body["totals"] == {"patient": 4, "staff": 2}
    assert rows(body) == {
        "communication": (2, 1, None),
        "safety": (1, 2, None),
        "environment": (1, 0, "patient"),
    }
    with app.state.sessionmaker() as session:
        assert "view_compare" in session.scalars(select(ActivityLog.action)).all()


def test_by_stage_and_unit(app, client) -> None:
    seed(app)
    headers = login(client, "analyst")
    by_stage = client.get("/compare", params={"by": "stage"}, headers=headers).json()
    assert rows(by_stage) == {"discharge_and_transfers": (2, 0, "patient"), "care_on_the_ward": (2, 2, None)}
    by_unit = client.get("/compare", params={"by": "unit"}, headers=headers).json()
    assert rows(by_unit) == {"4B": (2, 2, None), "3A": (2, 0, "patient")}
    assert client.get("/compare", params={"by": "colour"}, headers=headers).status_code == 422


def test_filters(app, client) -> None:
    seed(app)
    headers = login(client, "analyst")
    body = client.get("/compare", params={"unit": "4b", "date_from": "2026-10-15"}, headers=headers).json()
    assert body["unit"] == "4B"
    assert rows(body) == {"communication": (1, 0, "patient"), "safety": (1, 1, None)}
    body = client.get("/compare", params={"by": "unit", "date_to": "2026-10-31"}, headers=headers).json()
    assert rows(body) == {"3A": (2, 0, "patient"), "4B": (1, 1, None)}
    bad = client.get("/compare", params={"date_from": "2026-11-02", "date_to": "2026-11-01"}, headers=headers)
    assert bad.status_code == 422


def test_manager_only_gets_their_unit(app, client) -> None:
    seed(app)
    headers = login(client, "manager4b")
    body = client.get("/compare", params={"by": "unit"}, headers=headers).json()
    assert body["unit"] == "4B" and rows(body) == {"4B": (2, 2, None)}
    assert client.get("/compare", params={"unit": "3A"}, headers=headers).status_code == 403


def test_compare_needs_login(client) -> None:
    assert client.get("/compare").status_code == 401
