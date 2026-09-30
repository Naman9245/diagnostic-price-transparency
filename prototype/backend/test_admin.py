"""What the admin dashboard changes: prices, doctors' fees and uploaded price sheets."""

import pytest

import admin
from store import today

TODAY = today().isoformat()


def upload(client, filename, content):
    """Upload a file as Jacaranda's price sheet."""
    files = {"file": (filename, content)}
    return client.post("/price-sheets/extract", data={"hospital_id": "jacaranda"}, files=files)


def test_an_edited_price_records_its_source_and_date(client):
    response = client.patch("/hospitals/copperpod/prices", json={"prices": {"cbc": 199}})
    assert response.status_code == 200
    assert response.json() == client.get("/hospitals/copperpod").json()
    price = response.json()["prices"]["cbc"]
    assert price == {"amount": 199, "source": "Edited in the admin dashboard", "as_of": TODAY}


@pytest.mark.parametrize(
    "body",
    [
        {"prices": {"cbc": 199, "lipid": 0}},  # one price out of range
        {"prices": {"cbc": 199, "nope": 100}},  # one unknown test
        {"prices": {"cbc": True}},  # JSON true isn't ₹1
        {"prices": {}},
        {"prices": {"cbc": 199}, "source": "  "},  # every price says where it came from
    ],
)
def test_a_bad_price_edit_changes_nothing(client, body):
    before = client.get("/hospitals/copperpod").json()
    assert client.patch("/hospitals/copperpod/prices", json=body).status_code == 422
    assert client.get("/hospitals/copperpod").json() == before


def test_an_edited_fee_records_its_source_and_date(client):
    body = {"fee": 1500, "source": "Phoned in by the hospital"}
    response = client.patch("/doctors/ananya-rao/fee", json=body)
    assert response.status_code == 200
    assert response.json() == client.get("/doctors/ananya-rao").json()
    fee = response.json()["fee"]
    assert fee == {"amount": 1500, "source": "Phoned in by the hospital", "as_of": TODAY}


@pytest.mark.parametrize(
    "body", [{"fee": 0}, {"fee": 100_001}, {"fee": True}, {"fee": 900, "source": ""}]
)
def test_a_bad_fee_edit_changes_nothing(client, body):
    before = client.get("/doctors/ananya-rao").json()
    assert client.patch("/doctors/ananya-rao/fee", json=body).status_code == 422
    assert client.get("/doctors/ananya-rao").json() == before


def test_price_sheet_names_are_matched_to_tests(client):
    response = upload(client, "rate-card.pdf", b"%PDF-1.4 demo")
    assert response.status_code == 200
    assert response.json()["size_bytes"] == len(b"%PDF-1.4 demo")
    rows = {row["raw_name"]: row for row in response.json()["rows"]}

    assert rows["COMPLETE BLOOD COUNT (CBC)"]["match"] == "exact"
    assert rows["X-RAY CHEST PA VIEW"]["test_id"] == "xray_chest"
    assert rows["GLYCOSYLATED HB (HBA1C)"]["match"] == "review"
    assert rows["GLYCOSYLATED HB (HBA1C)"]["test_id"] == "hba1c"
    # Looks like a CBC and isn't one, so it must never skip review.
    assert rows["RED BLOOD CELL COUNT"]["match"] != "exact"
    assert rows["GENERAL WARD BED CHARGES (PER DAY)"]["match"] == "none"


def test_price_sheet_refuses_other_file_types(client):
    assert upload(client, "setup.exe", b"MZ").status_code == 415


def test_price_sheet_refuses_files_over_the_limit(client, monkeypatch):
    monkeypatch.setattr(admin, "MAX_SHEET_BYTES", 4)
    assert upload(client, "rate-card.pdf", b"%PDF-1.4 demo").status_code == 413
