"""Shared set-up for the API tests. Run them with `pytest` from this folder."""

import pytest
from fastapi.testclient import TestClient

import main
from store import reset_state


@pytest.fixture(autouse=True)
def fresh_data():
    """Every test starts from mock_data.json, not from the last test's edits."""
    reset_state()


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture
def sign_in(client):
    """sign_in(phone) signs in with the demo code and returns the headers that carry the token."""

    def sign_in(phone="9876543210"):
        response = client.post("/auth/verify", json={"phone": phone, "code": "123456"})
        return {"Authorization": f"Bearer {response.json()['token']}"}

    return sign_in
