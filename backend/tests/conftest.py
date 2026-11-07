from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from kaizen.api.app import create_app
from kaizen.api.auth import hash_password
from kaizen.db import Role, User

PASSWORD = "test-password-123"


@pytest.fixture
def app(tmp_path):
    return create_app(f"sqlite:///{tmp_path / 'test.db'}")


@pytest.fixture
def client(app):
    with app.state.sessionmaker() as session:
        session.add_all(
            [
                User(username="admin", password_hash=hash_password(PASSWORD), role=Role.ADMIN),
                User(username="analyst", password_hash=hash_password(PASSWORD), role=Role.QI),
                User(username="manager4b", password_hash=hash_password(PASSWORD), role=Role.MANAGER, unit="4B"),
            ]
        )
        session.commit()
    return TestClient(app)


def login(client: TestClient, username: str) -> dict[str, str]:
    response = client.post("/auth/login", json={"username": username, "password": PASSWORD})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['token']}"}
