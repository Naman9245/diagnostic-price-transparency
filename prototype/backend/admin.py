"""What the admin dashboard changes: prices, doctors' fees, and uploaded price sheets."""

from __future__ import annotations

import difflib
import re
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, StrictInt, StringConstraints

from catalog import doctor_view
from store import DEFAULT_LAT, DEFAULT_LNG, find, priced, state, today, with_distance

router = APIRouter(tags=["Admin"])

# File types the mock price-sheet reader pretends to understand.
SHEET_TYPES = {".pdf", ".xlsx", ".xls", ".csv", ".jpg", ".jpeg", ".png"}
MAX_SHEET_BYTES = 10 * 1024 * 1024

# Whole rupees. Strict, because pydantic would otherwise read a JSON true as ₹1.
Rupees = Annotated[StrictInt, Field(ge=1, le=100_000)]
# Where an edited number came from. The app shows it beside the number, so never blank.
Source = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Edit(BaseModel):
    """What every edit carries: where its numbers came from."""

    source: Source = "Edited in the admin dashboard"


class PriceUpdate(Edit):
    """New prices for one hospital, keyed by test id."""

    prices: dict[str, Rupees] = Field(min_length=1, examples=[{"cbc": 299, "lipid": 649}])


class FeeUpdate(Edit):
    """A doctor's new consultation fee."""

    fee: Rupees


@router.patch("/hospitals/{hospital_id}/prices")
def update_prices(hospital_id: str, update: PriceUpdate):
    """Set one or more prices. Each one records where it came from and when.

    All or nothing: if any test id or amount is wrong, no price changes.
    """
    hospital = find("hospitals", hospital_id)
    for test_id in update.prices:
        if test_id not in state["tests"]:
            raise HTTPException(422, f"No test with id '{test_id}'.")
    as_of = today().isoformat()
    for test_id, amount in update.prices.items():
        hospital["prices"][test_id] = priced(amount, update.source, as_of)
    return with_distance(hospital, DEFAULT_LAT, DEFAULT_LNG)


@router.patch("/doctors/{doctor_id}/fee")
def update_fee(doctor_id: str, update: FeeUpdate):
    """Set a doctor's consultation fee. Like a price, it records where it came from and when."""
    doctor = find("doctors", doctor_id)
    doctor["fee"] = priced(update.fee, update.source, today().isoformat())
    return doctor_view(doctor, DEFAULT_LAT, DEFAULT_LNG)


# What the mock reader "finds" in any uploaded sheet: each name exactly as it
# was printed, and its price. Real sheets are whole hospital catalogues, so
# some rows aren't diagnostic tests at all.
MOCK_SHEET_ROWS = [
    ("COMPLETE BLOOD COUNT (CBC)", 330),
    ("LIPID PROFILE", 720),
    ("THYROID PROFILE (T3, T4, TSH)", 560),
    ("GLYCOSYLATED HB (HBA1C)", 450),
    ("VITAMIN D (25-OH)", 1250),
    ("RED BLOOD CELL COUNT", 150),
    ("LFT", 640),
    ("RENAL FUNCTION TEST (RFT)", 690),
    ("X-RAY CHEST PA VIEW", 400),
    ("2D ECHOCARDIOGRAPHY", 2400),
    ("GENERAL WARD BED CHARGES (PER DAY)", 1800),
]


def normalise(name: str) -> str:
    """Lowercase, punctuation to spaces, squeeze spaces: 'X-Ray  Chest' -> 'x ray chest'."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", name.lower()).split())


def match_test_name(raw_name: str) -> dict:
    """Map a name as printed on a price sheet to one of our tests.

    exact:  it is one of the test's known names, so it is safe to publish.
    review: it only looks like one. A person must confirm it first, because a
            similar name is not always the same test (RED BLOOD CELL COUNT
            looks like COMPLETE BLOOD COUNT and is a different test).
    none:   nothing is close, such as bed charges, which aren't a test.
    """
    known_names = {
        normalise(name): test["id"]
        for test in state["tests"].values()
        for name in [test["name"], *test["aliases"]]
    }
    key = normalise(raw_name)
    if key in known_names:
        return {"match": "exact", "test_id": known_names[key], "similarity": 1.0}
    close = difflib.get_close_matches(key, known_names, n=1)  # stdlib's default cutoff, 0.6
    if close:
        similarity = difflib.SequenceMatcher(None, key, close[0]).ratio()
        return {
            "match": "review",
            "test_id": known_names[close[0]],
            "similarity": round(similarity, 2),
        }
    return {"match": "none", "test_id": None, "similarity": None}


@router.post("/price-sheets/extract")
def extract_price_sheet(hospital_id: Annotated[str, Form()], file: Annotated[UploadFile, File()]):
    """Pretend to read an uploaded rate card, then match each name to a test.

    The reading is mocked: whatever you upload, the same rows come back. The
    name matching is real, and it's the part worth showing.
    """
    hospital = find("hospitals", hospital_id)
    if Path(file.filename or "").suffix.lower() not in SHEET_TYPES:
        raise HTTPException(415, "Upload a PDF, Excel, CSV, JPG or PNG file.")
    if file.size > MAX_SHEET_BYTES:
        raise HTTPException(413, "That file is over 10 MB.")

    rows = []
    for line, (raw_name, amount) in enumerate(MOCK_SHEET_ROWS, start=1):
        match = match_test_name(raw_name)
        test = state["tests"].get(match["test_id"])
        current = hospital["prices"].get(match["test_id"])
        rows.append(
            {
                "line": line,
                "raw_name": raw_name,
                "price": amount,
                **match,
                "test_name": test["name"] if test else None,
                "current_price": current["amount"] if current else None,
            }
        )
    return {
        "file_name": file.filename,
        "size_bytes": file.size,
        "hospital_id": hospital_id,
        "hospital_name": hospital["name"],
        "mock": True,
        "rows": rows,
    }
