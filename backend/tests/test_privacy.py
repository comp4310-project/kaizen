"""NFR1: original text is never stored, roles are enforced, and actions are logged.

The canary test imports comments holding known fake details through both the CSV upload
and the public form, then reads every column of every table and checks that none of the
details are there. test_classify.py runs the same check on what is sent to Claude.
"""

from __future__ import annotations

from sqlalchemy import select

from kaizen.db import ActivityLog, Base
from tests.conftest import login
from tests.test_import import make_csv

CANARIES = {
    "Bartholomew Quince": "Nurse Bartholomew Quince",
    "807-555-0188": "call 807-555-0188",
    "quince.family@example.com": "email quince.family@example.com",
    "4532-015-112": "health card 4532-015-112",
    "M7781234": "MRN M7781234",
    "March 14": "on March 14",
}


def dump_database(app) -> str:
    parts = []
    with app.state.sessionmaker() as session:
        for table in Base.metadata.sorted_tables:
            for row in session.execute(select(table)).all():
                parts.extend(str(value) for value in row)
    return "\n".join(parts)


def test_original_text_is_never_stored(app, client) -> None:
    text = "My dad was seen by " + ", ".join(CANARIES.values()) + "."
    upload = client.post(
        "/imports",
        files={"file": ("Bartholomew Quince.csv", make_csv([{"text": text, "source": "family", "unit": "4B", "date": "2026-10-02"}]))},
        headers=login(client, "analyst"),
    )
    assert upload.status_code == 201, upload.text
    form = client.post("/feedback", json={"text": text, "source": "patient", "unit": "5A", "date": "2026-10-03"})
    assert form.status_code == 201, form.text

    stored = dump_database(app)
    assert "<PERSON>" in stored and "<PHONE>" in stored
    leaked = [value for value in CANARIES if value in stored]
    assert leaked == []


def test_form_needs_no_login_but_reading_does(client) -> None:
    ok = client.post("/feedback", json={"text": "Too noisy at night", "source": "patient", "unit": "4B"})
    assert ok.status_code == 201
    assert client.get("/comments").status_code == 401


def test_form_rejects_bad_input_without_echoing_it(client) -> None:
    response = client.post("/feedback", json={"text": "Nurse Rose", "source": "patient", "unit": "nowhere"})
    assert response.status_code == 422
    assert "Rose" not in response.text


def test_manager_sees_only_own_unit(client) -> None:
    for unit in ("4B", "5A"):
        client.post("/feedback", json={"text": f"Noise on {unit}", "source": "patient", "unit": unit})
    headers = login(client, "manager4b")

    mine = client.get("/comments", headers=headers).json()
    assert {c["unit"] for c in mine["comments"]} == {"4B"}
    assert client.get("/comments", params={"unit": "5A"}, headers=headers).status_code == 403

    analyst = client.get("/comments", headers=login(client, "analyst")).json()
    assert {c["unit"] for c in analyst["comments"]} == {"4B", "5A"}


def test_only_admin_creates_accounts(client) -> None:
    new = {"username": "qi2", "password": "another-password-1", "role": "qi"}
    assert client.post("/users", json=new, headers=login(client, "analyst")).status_code == 403
    assert client.post("/users", json=new, headers=login(client, "admin")).status_code == 201
    manager_without_unit = {"username": "m2", "password": "another-password-1", "role": "manager"}
    assert client.post("/users", json=manager_without_unit, headers=login(client, "admin")).status_code == 422


def test_managers_cannot_upload(client) -> None:
    response = client.post(
        "/imports",
        files={"file": ("a.csv", b"text,source,unit,date\n")},
        headers=login(client, "manager4b"),
    )
    assert response.status_code == 403


def test_wrong_password_and_bad_token_are_refused(client) -> None:
    assert client.post("/auth/login", json={"username": "admin", "password": "nope"}).status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer made-up"}).status_code == 401


def test_actions_are_logged(app, client) -> None:
    headers = login(client, "analyst")
    client.post("/feedback", json={"text": "Bed was dirty", "source": "patient", "unit": "4B"})
    client.get("/comments", headers=headers)
    with app.state.sessionmaker() as session:
        actions = [row.action for row in session.scalars(select(ActivityLog).order_by(ActivityLog.id))]
    assert actions == ["login", "submit_form", "view_comments"]


def test_passwords_are_hashed(app, client) -> None:
    from tests.conftest import PASSWORD

    assert PASSWORD not in dump_database(app)
