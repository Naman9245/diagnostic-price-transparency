"""Signing in with a mobile number and the demo code."""

import pytest

PHONE = "9876543210"


def test_signing_in_with_the_demo_code(client):
    sent = client.post("/auth/code", json={"phone": PHONE}).json()
    assert sent == {"sent_to": PHONE, "demo_code": "123456"}
    signed_in = client.post("/auth/verify", json={"phone": PHONE, "code": "123456"}).json()
    assert signed_in["user"] == {"phone": PHONE, "name": None}
    me = client.get("/me", headers={"Authorization": f"Bearer {signed_in['token']}"})
    assert me.json()["phone"] == PHONE


def test_a_wrong_code_is_refused(client):
    assert client.post("/auth/verify", json={"phone": PHONE, "code": "000000"}).status_code == 401


@pytest.mark.parametrize(
    "phone",
    # The last is 9 then Devanagari digits: one phone written two ways must not be two accounts.
    ["98765", "5876543210", "98765432101", "9८७६५४३२१०"],
)
def test_an_invalid_phone_number_is_refused(client, phone):
    assert client.post("/auth/code", json={"phone": phone}).status_code == 422
    assert client.post("/auth/verify", json={"phone": phone, "code": "123456"}).status_code == 422


def test_the_first_sign_in_has_no_name_until_one_is_set(client, sign_in):
    headers = sign_in()
    assert client.get("/me", headers=headers).json()["name"] is None
    assert client.put("/me", json={"name": "  Asha  "}, headers=headers).json()["name"] == "Asha"
    assert client.put("/me", json={"name": "   "}, headers=headers).status_code == 422
    # Signing in again brings back the same account, name and all.
    assert client.get("/me", headers=sign_in()).json()["name"] == "Asha"


def test_me_needs_a_valid_token(client):
    assert client.get("/me").status_code == 401
    assert client.get("/me", headers={"Authorization": "Bearer made-up"}).status_code == 401


def test_signing_out_ends_the_session(client, sign_in):
    headers = sign_in()
    assert client.post("/auth/sign-out", headers=headers).status_code == 204
    assert client.get("/me", headers=headers).status_code == 401
