"""Booking a test or a doctor's appointment: signed-in users, partner hospitals only.

It's a mock, so nobody is notified. The rules are real, though: the app can't
promise a slot the hospital wouldn't give.
"""

from __future__ import annotations

import random
import string
from datetime import date, datetime, time
from typing import Self

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, model_validator

from auth import SignedIn
from store import IST, WEEKDAYS, find, state, today

router = APIRouter(tags=["Bookings"])


class BookingRequest(BaseModel):
    """A test at a hospital, or an appointment with a doctor. Send one or the other."""

    test_id: str | None = None
    hospital_id: str | None = None
    doctor_id: str | None = None
    date: date
    time: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$", examples=["08:30"])
    home_collection: bool = False

    @model_validator(mode="after")
    def _test_or_doctor(self) -> Self:
        """One booking, one thing. A test also needs a hospital; a doctor has their own."""
        if bool(self.test_id) == bool(self.doctor_id):
            raise ValueError("Book either a test (test_id) or a doctor (doctor_id).")
        if self.test_id and not self.hospital_id:
            raise ValueError("Say which hospital to book the test at (hospital_id).")
        return self


def bookable(hospital: dict) -> dict:
    """The hospital, if it takes bookings. Only partners do: nobody else would receive one."""
    if not hospital["partner"]:
        raise HTTPException(
            403, f"{hospital['name']} isn't a RateCard partner, so it can't be booked here."
        )
    return hospital


def book_test(request: BookingRequest) -> tuple[dict, dict]:
    """The hospital, and the test's side of the booking, if the hospital can do it as asked."""
    test = find("tests", request.test_id)
    hospital = bookable(find("hospitals", request.hospital_id))
    price = hospital["prices"].get(test["id"])
    if price is None:
        raise HTTPException(422, f"{hospital['name']} doesn't offer {test['name']}.")
    if request.home_collection and not (hospital["home_collection"] and test["home_collection"]):
        raise HTTPException(
            422, f"{hospital['name']} can't collect a {test['short_name']} sample at home."
        )
    return hospital, {
        "kind": "test",
        "item_id": test["id"],
        "title": test["name"],
        "subtitle": test["short_name"],
        "price": price["amount"],
        "home_collection_fee": hospital["home_collection_fee"] if request.home_collection else 0,
        "preparation": test["preparation"],
    }


def book_doctor(request: BookingRequest) -> tuple[dict, dict]:
    """The doctor's hospital, and their side of the booking, if they're in at that time."""
    doctor = find("doctors", request.doctor_id)
    hospital = bookable(state["hospitals"][doctor["hospital_id"]])
    if request.home_collection:
        raise HTTPException(422, f"{doctor['name']} sees patients at the hospital, not at home.")
    if WEEKDAYS[request.date.weekday()] not in doctor["days"]:
        raise HTTPException(422, f"{doctor['name']} doesn't see patients on {request.date:%A}s.")
    if not any(request.time in times for times in doctor["slots"].values()):
        raise HTTPException(422, f"{doctor['name']} has no {request.time} slot.")
    return hospital, {
        "kind": "doctor",
        "item_id": doctor["id"],
        "title": doctor["name"],
        "subtitle": state["specialties"][doctor["specialty"]]["name"],
        "price": doctor["fee"]["amount"],
        "home_collection_fee": 0,
        "preparation": "Bring earlier prescriptions and any recent test reports",
    }


@router.post("/bookings", status_code=201)
def create_booking(request: BookingRequest, user: SignedIn):
    """Book a test or a doctor at a partner hospital, within the next two weeks.

    Only partners take bookings. Everyone else is listed so you can compare
    prices, but nobody there would receive the booking.
    """
    when = datetime.combine(request.date, time.fromisoformat(request.time), IST)
    if when <= datetime.now(IST):
        raise HTTPException(422, "That time has passed. Pick a later slot.")
    if (request.date - today()).days > 14:
        raise HTTPException(422, "Pick a date in the next two weeks.")
    hospital, item = book_test(request) if request.test_id else book_doctor(request)
    booking = {
        "id": "RC-" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6)),
        "status": "confirmed",
        "user": user["phone"],
        **item,
        "hospital_id": hospital["id"],
        "hospital_name": hospital["name"],
        "hospital_area": hospital["area"],
        "brand_color": hospital["brand_color"],
        "date": request.date.isoformat(),
        "time": request.time,
        "home_collection": request.home_collection,
        "total": item["price"] + item["home_collection_fee"],
        "demo": True,
    }
    state["bookings"].append(booking)
    return booking


@router.get("/bookings")
def list_bookings(user: SignedIn):
    """Your bookings, soonest first."""
    mine = (b for b in state["bookings"] if b["user"] == user["phone"])
    return sorted(mine, key=lambda b: (b["date"], b["time"]))
