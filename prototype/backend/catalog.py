"""What the app reads: tests, hospitals, specialties and doctors."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from store import DEFAULT_LAT, DEFAULT_LNG, find, state, with_distance

router = APIRouter(tags=["Tests, hospitals and doctors"])

# Where you are. Bounded, because a distance from NaN or infinity can't be sent as JSON.
Lat = Annotated[float, Query(ge=-90, le=90)]
Lng = Annotated[float, Query(ge=-180, le=180)]


def price_range(amounts: list[int], prefix: str) -> dict:
    """{"min_<prefix>": ..., "max_<prefix>": ...} for a list of prices (None when empty)."""
    return {
        f"min_{prefix}": min(amounts, default=None),
        f"max_{prefix}": max(amounts, default=None),
    }


@router.get("/tests")
def list_tests():
    """Every test, with how many hospitals offer it and its price range."""
    result = []
    for test in state["tests"].values():
        amounts = [
            hospital["prices"][test["id"]]["amount"]
            for hospital in state["hospitals"].values()
            if test["id"] in hospital["prices"]
        ]
        result.append({**test, "lab_count": len(amounts), **price_range(amounts, "price")})
    return result


@router.get("/hospitals")
def list_hospitals(test_id: str | None = None, lat: Lat = DEFAULT_LAT, lng: Lng = DEFAULT_LNG):
    """Hospitals, each with its distance from (lat, lng).

    With `test_id`, only the hospitals that offer that test, cheapest first.
    Without it, every hospital in name order, which is what the admin table
    shows.
    """
    hospitals = [with_distance(h, lat, lng) for h in state["hospitals"].values()]
    if test_id is None:
        return sorted(hospitals, key=lambda h: h["name"])
    find("tests", test_id)  # 404 for an unknown test
    offering = [h for h in hospitals if test_id in h["prices"]]
    return sorted(offering, key=lambda h: h["prices"][test_id]["amount"])


@router.get("/hospitals/{hospital_id}")
def get_hospital(hospital_id: str, lat: Lat = DEFAULT_LAT, lng: Lng = DEFAULT_LNG):
    """One hospital with all of its prices."""
    return with_distance(find("hospitals", hospital_id), lat, lng)


@router.get("/specialties")
def list_specialties():
    """Every specialty, with how many doctors practise it and their fee range."""
    result = []
    for specialty in state["specialties"].values():
        fees = [
            doctor["fee"]["amount"]
            for doctor in state["doctors"].values()
            if doctor["specialty"] == specialty["id"]
        ]
        result.append({**specialty, "doctor_count": len(fees), **price_range(fees, "fee")})
    return result


def doctor_view(doctor: dict, lat: float, lng: float) -> dict:
    """A doctor, with their specialty's name and their hospital's details and distance."""
    hospital = with_distance(state["hospitals"][doctor["hospital_id"]], lat, lng)
    keep = ("id", "name", "area", "address", "brand_color", "partner", "distance_km")
    return {
        **doctor,
        "specialty_name": state["specialties"][doctor["specialty"]]["name"],
        "hospital": {key: hospital[key] for key in keep},
    }


@router.get("/doctors")
def list_doctors(
    specialty: str | None = None,
    hospital_id: str | None = None,
    lat: Lat = DEFAULT_LAT,
    lng: Lng = DEFAULT_LNG,
):
    """Doctors, nearest hospital first. Filter by specialty, hospital, or both.

    Only partner hospitals list their doctors (store.load_state refuses any
    other): they publish their own timetables, which is what makes a booking real.
    """
    if specialty is not None:
        find("specialties", specialty)
    if hospital_id is not None:
        find("hospitals", hospital_id)
    doctors = [
        doctor_view(doctor, lat, lng)
        for doctor in state["doctors"].values()
        if specialty in (None, doctor["specialty"]) and hospital_id in (None, doctor["hospital_id"])
    ]
    return sorted(doctors, key=lambda d: (d["hospital"]["distance_km"], d["name"]))


@router.get("/doctors/{doctor_id}")
def get_doctor(doctor_id: str, lat: Lat = DEFAULT_LAT, lng: Lng = DEFAULT_LNG):
    """One doctor, with their fee, timetable and hospital."""
    return doctor_view(find("doctors", doctor_id), lat, lng)
