"""What the app reads: tests, hospitals, specialties and doctors."""

import json

import pytest

import store

# Every field each response carries, so dropping or renaming one fails a test.
SPECIALTY_FIELDS = {"id", "name", "about", "doctor_count", "min_fee", "max_fee"}
DOCTOR_FIELDS = (
    {"id", "name", "about", "qualifications", "experience_years", "languages", "demo"}
    | {"specialty", "specialty_name", "rating", "reviews", "hospital_id", "hospital"}
    | {"days", "slots", "fee"}
)
DOCTOR_HOSPITAL_FIELDS = {"id", "name", "area", "address", "brand_color", "partner", "distance_km"}


def test_every_test_has_a_price_range(client):
    tests = client.get("/tests").json()
    assert len(tests) == 8
    for test in tests:
        assert test["lab_count"] > 0
        assert test["min_price"] <= test["max_price"]


@pytest.mark.parametrize(
    ("path", "order"),
    [
        ("/hospitals", lambda h: h["name"]),
        ("/hospitals?test_id=lipid", lambda h: h["prices"]["lipid"]["amount"]),  # cheapest first
        ("/doctors", lambda d: (d["hospital"]["distance_km"], d["name"])),  # nearest first
    ],
)
def test_lists_come_in_order(client, path, order):
    listed = client.get(path).json()
    assert listed == sorted(listed, key=order)


def test_hospitals_without_the_test_are_left_out(client):
    hospitals = client.get("/hospitals", params={"test_id": "xray_chest"}).json()
    assert len(hospitals) == 8
    assert all("xray_chest" in h["prices"] for h in hospitals)


@pytest.mark.parametrize(
    "path",
    [
        "/hospitals?test_id=nope",
        "/hospitals/nowhere",
        "/doctors?specialty=astrology",
        "/doctors?hospital_id=nowhere",
        "/doctors/nobody",
    ],
)
def test_unknown_ids_are_a_404(client, path):
    assert client.get(path).status_code == 404


def test_distance_depends_on_where_you_are(client):
    whitefield = {"lat": 12.9698, "lng": 77.7500}
    hospitals = client.get("/hospitals", params={"test_id": "cbc", **whitefield}).json()
    assert min(hospitals, key=lambda h: h["distance_km"])["id"] == "tabebuia"


@pytest.mark.parametrize("where", ["lat=nan", "lng=inf", "lat=91", "lng=-181"])
@pytest.mark.parametrize(
    "path", ["/hospitals", "/hospitals/jacaranda", "/doctors", "/doctors/ananya-rao"]
)
def test_impossible_coordinates_are_refused(client, path, where):
    assert client.get(f"{path}?{where}").status_code == 422


def test_specialties_count_their_doctors_and_fee_range(client):
    specialties = {s["id"]: s for s in client.get("/specialties").json()}
    assert sum(s["doctor_count"] for s in specialties.values()) == 17
    general = specialties["general"]
    assert (general["doctor_count"], general["min_fee"], general["max_fee"]) == (4, 400, 600)


@pytest.mark.parametrize(
    ("path", "fields"), [("/specialties", SPECIALTY_FIELDS), ("/doctors", DOCTOR_FIELDS)]
)
def test_responses_carry_exactly_their_fields(client, path, fields):
    assert all(item.keys() == fields for item in client.get(path).json())


def test_every_hospital_and_doctor_is_a_demo(client):
    listed = client.get("/hospitals").json() + client.get("/doctors").json()
    assert all(item["demo"] for item in listed)


def test_every_doctor_works_at_a_partner_and_has_a_sourced_fee(client):
    for doctor in client.get("/doctors").json():
        assert doctor["hospital"]["partner"]
        assert doctor["hospital"].keys() == DOCTOR_HOSPITAL_FIELDS
        assert doctor["fee"].keys() == {"amount", "source", "as_of"}


def test_a_doctor_at_a_non_partner_hospital_is_refused_at_load(tmp_path, monkeypatch):
    raw = json.loads(store.DATA_FILE.read_text(encoding="utf-8"))
    raw["doctors"][0]["hospital_id"] = "tabebuia"
    data_file = tmp_path / "mock_data.json"
    data_file.write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(store, "DATA_FILE", data_file)
    with pytest.raises(ValueError, match="isn't a partner"):
        store.load_state()


def test_doctors_filter_by_specialty_and_hospital(client):
    def ids(**params):
        return {d["id"] for d in client.get("/doctors", params=params).json()}

    assert ids(specialty="cardiology") == {"ananya-rao", "harish-reddy"}
    assert ids(hospital_id="copperpod") == {"nikhil-verma", "sana-sheikh", "rohan-dsouza"}
    assert ids(specialty="general", hospital_id="copperpod") == {"nikhil-verma"}
