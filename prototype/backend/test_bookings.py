"""Booking tests and doctors: signed-in users, partner hospitals, the next two weeks."""

import re
from datetime import timedelta

import pytest

from store import WEEKDAYS, today

# Every field a booking carries, so dropping or renaming one fails a test.
BOOKING_FIELDS = (
    {"id", "status", "user", "kind", "item_id", "title", "subtitle", "demo"}
    | {"hospital_id", "hospital_name", "hospital_area", "brand_color"}
    | {"date", "time", "home_collection", "price", "home_collection_fee", "total", "preparation"}
)


def in_days(days: int) -> str:
    """The date `days` from today, as the API writes it."""
    return (today() + timedelta(days=days)).isoformat()


def next_day(weekday: str) -> str:
    """The first date after today that falls on a weekday such as "Mon"."""
    return next(in_days(n) for n in range(1, 8) if WEEKDAYS[(today().weekday() + n) % 7] == weekday)


@pytest.fixture
def book(client, sign_in):
    """book(**fields) books as a signed-in user and returns the response.

    It books a lipid profile at Jacaranda tomorrow at 08:00 unless told otherwise:
    tomorrow, so the slot hasn't passed whatever time the tests run. Pass
    doctor_id to book a doctor instead, and phone to book as someone else.
    """

    def book(phone="9876543210", **fields):
        body = {"date": in_days(1), "time": "08:00"}
        if "doctor_id" not in fields:
            body |= {"test_id": "lipid", "hospital_id": "jacaranda"}
        return client.post("/bookings", json=body | fields, headers=sign_in(phone))

    return book


def test_booking_a_partner_hospital(book):
    response = book()
    assert response.status_code == 201
    booking = response.json()
    assert booking.keys() == BOOKING_FIELDS
    assert booking["status"] == "confirmed"
    assert booking["total"] == 1150
    assert re.fullmatch(r"RC-[A-Z0-9]{6}", booking["id"])
    assert (booking["user"], booking["kind"]) == ("9876543210", "test")
    assert (booking["title"], booking["subtitle"]) == ("Lipid Profile", "Lipid")


def test_bookings_are_listed_soonest_first(client, sign_in, book):
    slots = [(in_days(2), "09:00"), (in_days(1), "18:00"), (in_days(1), "08:00")]
    for day, time in slots:
        book(date=day, time=time)
    listed = client.get("/bookings", headers=sign_in()).json()
    assert [(b["date"], b["time"]) for b in listed] == sorted(slots)
    assert listed[0]["hospital_area"] == "Koramangala"


def test_each_user_sees_only_their_own_bookings(client, sign_in, book):
    book(time="08:00")
    book(phone="9123456789", time="09:00")
    for phone, time in [("9876543210", "08:00"), ("9123456789", "09:00")]:
        listed = client.get("/bookings", headers=sign_in(phone)).json()
        assert [(b["user"], b["time"]) for b in listed] == [(phone, time)]


def test_bookings_need_a_sign_in(client):
    assert client.get("/bookings").status_code == 401
    body = {"test_id": "lipid", "hospital_id": "jacaranda", "date": in_days(1), "time": "08:00"}
    assert client.post("/bookings", json=body).status_code == 401


@pytest.mark.parametrize(("at_home", "fee"), [(True, 99), (False, 0)])
def test_only_home_collection_adds_the_hospitals_fee(book, at_home, fee):
    booking = book(hospital_id="copperpod", test_id="cbc", home_collection=at_home).json()
    assert (booking["home_collection_fee"], booking["total"]) == (fee, 240 + fee)


# An x-ray can't be taken at home anywhere, and Flame Tree collects nothing at home.
@pytest.mark.parametrize(
    ("hospital_id", "test_id"), [("jacaranda", "xray_chest"), ("flametree", "lipid")]
)
def test_home_collection_needs_both_the_test_and_the_hospital(book, hospital_id, test_id):
    assert book(hospital_id=hospital_id, test_id=test_id, home_collection=True).status_code == 422


def test_non_partner_hospitals_cannot_be_booked(book):
    assert book(hospital_id="tabebuia").status_code == 403


def test_bookings_open_two_weeks_ahead(book):
    assert book(date=in_days(14)).status_code == 201


def test_dates_after_the_next_two_weeks_are_refused(book):
    response = book(date=in_days(15))
    assert response.status_code == 422
    assert response.json()["detail"] == "Pick a date in the next two weeks."


@pytest.mark.parametrize(("days", "time"), [(-1, "08:00"), (0, "00:00")])
def test_times_that_have_passed_are_refused(book, days, time):
    response = book(date=in_days(days), time=time)
    assert response.status_code == 422
    assert response.json()["detail"] == "That time has passed. Pick a later slot."


@pytest.mark.parametrize("time", ["25:99", "24:00", "8:00"])
def test_impossible_times_are_refused(book, time):
    assert book(time=time).status_code == 422


@pytest.mark.parametrize(
    "fields",
    [
        {"test_id": None},  # neither a test nor a doctor
        {"doctor_id": "ananya-rao", "test_id": "lipid", "hospital_id": "jacaranda"},  # both
        {"hospital_id": None},  # a test, but nowhere to do it
    ],
)
def test_a_booking_is_for_one_test_or_one_doctor(book, fields):
    assert book(**fields).status_code == 422


def test_booking_a_doctor_on_a_day_they_work(book):
    response = book(doctor_id="ananya-rao", date=next_day("Mon"), time="09:00")
    assert response.status_code == 201
    booking = response.json()
    assert booking.keys() == BOOKING_FIELDS
    assert (booking["kind"], booking["item_id"]) == ("doctor", "ananya-rao")
    assert (booking["title"], booking["subtitle"]) == ("Dr. Ananya Rao", "Cardiology")
    assert booking["price"] == booking["total"] == 1200
    assert booking["hospital_id"] == "jacaranda"


@pytest.mark.parametrize(
    ("day", "time", "at_home", "detail"),
    [
        ("Tue", "09:00", False, "Dr. Ananya Rao doesn't see patients on Tuesdays."),
        ("Mon", "17:00", False, "Dr. Ananya Rao has no 17:00 slot."),
        ("Mon", "09:00", True, "Dr. Ananya Rao sees patients at the hospital, not at home."),
    ],
)
def test_a_doctor_is_booked_only_when_they_see_patients(book, day, time, at_home, detail):
    response = book(doctor_id="ananya-rao", date=next_day(day), time=time, home_collection=at_home)
    assert (response.status_code, response.json()["detail"]) == (422, detail)
