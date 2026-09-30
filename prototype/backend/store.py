"""The demo's data, held in memory, and the helpers every endpoint shares.

Everything comes from mock_data.json. Nothing is written to disk: price edits,
sign-ins and bookings disappear when the server restarts, which is what a demo
wants.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException

DATA_FILE = Path(__file__).with_name("mock_data.json")

# India has one time zone and no daylight saving, so a fixed offset is exact.
IST = timezone(timedelta(hours=5, minutes=30), "IST")

# Where "you" are when the app doesn't send a location: Koramangala.
DEFAULT_LAT, DEFAULT_LNG = 12.9352, 77.6245

# Weekday names as mock_data.json writes them, Monday first like date.weekday().
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def load_state() -> dict:
    """Read mock_data.json into the shape the endpoints use.

    The file stores prices compactly: each hospital's test prices as
    {test_id: rupees}, each doctor's fee as rupees, and the one rate card they
    all came from. In memory every price carries its own source and date,
    because editing one price changes where that price came from, not the card.
    """
    raw = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    cards, hospitals = {}, {}
    for hospital in raw["hospitals"]:
        card = cards[hospital["id"]] = hospital.pop("rate_card")
        hospital["prices"] = {
            test: priced(amount, **card) for test, amount in hospital["prices"].items()
        }
        hospitals[hospital["id"]] = hospital

    doctors = {}
    for doctor in raw["doctors"]:
        # Only partners list doctors: they publish the timetables a booking relies on.
        if not hospitals[doctor["hospital_id"]]["partner"]:
            raise ValueError(f"{doctor['id']} is listed at a hospital that isn't a partner.")
        doctor["fee"] = priced(doctor["fee"], **cards[doctor["hospital_id"]])
        # A doctor's sessions ("Morning", "Evening") become their actual time slots.
        doctor["slots"] = {name: raw["sessions"][name] for name in doctor.pop("sessions")}
        doctors[doctor["id"]] = doctor

    return {
        "tests": {test["id"]: test for test in raw["tests"]},
        "hospitals": hospitals,
        "specialties": {specialty["id"]: specialty for specialty in raw["specialties"]},
        "doctors": doctors,
        "bookings": [],
        "users": {},  # phone number -> user
        "sessions": {},  # sign-in token -> phone number
    }


def priced(amount: int, source: str, as_of: str) -> dict:
    """A price, with the source and date it came from."""
    return {"amount": amount, "source": source, "as_of": as_of}


state = load_state()


def reset_state() -> None:
    """Throw away every edit, sign-in and booking. The tests call this between cases."""
    state.clear()
    state.update(load_state())


def today() -> date:
    """Today in Bengaluru, whatever time zone the server itself runs in."""
    return datetime.now(IST).date()


_SINGULAR = {
    "tests": "test",
    "hospitals": "hospital",
    "doctors": "doctor",
    "specialties": "specialty",
}


def find(collection: str, item_id: str) -> dict:
    """One item from a collection ("tests", "doctors"...), or a 404 naming what's missing."""
    item = state[collection].get(item_id)
    if item is None:
        raise HTTPException(404, f"No {_SINGULAR[collection]} with id '{item_id}'.")
    return item


def distance_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance between two points on Earth (haversine formula)."""
    earth_radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return round(2 * earth_radius_km * math.asin(math.sqrt(a)), 1)


def with_distance(hospital: dict, lat: float, lng: float) -> dict:
    """A copy of the hospital with its distance from (lat, lng) added."""
    return {**hospital, "distance_km": distance_km(lat, lng, hospital["lat"], hospital["lng"])}
