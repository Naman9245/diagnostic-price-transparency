"""Signing in with a mobile number and a one-time code.

It's a demo: no text message is sent, and the code is always DEMO_CODE. The
first sign-in creates the account ("register once"); the app then asks for a
name. A sign-in token lasts until sign-out or a server restart.
"""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, StringConstraints

from store import state

DEMO_CODE = "123456"

router = APIRouter(tags=["Sign-in"])
bearer = HTTPBearer(auto_error=False, description="The token from POST /auth/verify")
Credentials = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]

# An Indian mobile number: ten digits, starting 6, 7, 8 or 9. [0-9], not \d, which also
# matches other scripts' digits and would let one phone make a second account.
Phone = Annotated[str, Field(pattern=r"^[6-9][0-9]{9}$", examples=["9876543210"])]


class CodeRequest(BaseModel):
    phone: Phone


class CodeCheck(BaseModel):
    phone: Phone
    code: str = Field(pattern=r"^[0-9]{6}$", examples=[DEMO_CODE])


class ProfileUpdate(BaseModel):
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


def current_user(credentials: Credentials) -> dict:
    """The signed-in user. Endpoints that need one depend on this."""
    phone = state["sessions"].get(credentials.credentials) if credentials else None
    if phone is None:
        raise HTTPException(401, "Sign in to continue.", headers={"WWW-Authenticate": "Bearer"})
    return state["users"][phone]


SignedIn = Annotated[dict, Depends(current_user)]


@router.post("/auth/code")
def send_code(request: CodeRequest):
    """Start signing in. A real app would text the code; the demo returns it."""
    return {"sent_to": request.phone, "demo_code": DEMO_CODE}


@router.post("/auth/verify")
def verify_code(request: CodeCheck):
    """Swap a phone number and the right code for a sign-in token.

    The first sign-in creates the account with no name yet, and the app asks
    for one next. Signing in again later brings back the same account.
    """
    if request.code != DEMO_CODE:
        raise HTTPException(401, "That code isn't right. In the demo it's always 123456.")
    user = state["users"].setdefault(request.phone, {"phone": request.phone, "name": None})
    token = secrets.token_urlsafe(24)
    state["sessions"][token] = request.phone
    return {"token": token, "user": user}


@router.get("/me")
def read_me(user: SignedIn):
    """Who's signed in."""
    return user


@router.put("/me")
def update_me(update: ProfileUpdate, user: SignedIn):
    """Set the signed-in user's name."""
    user["name"] = update.name
    return user


@router.post("/auth/sign-out", status_code=204)
def sign_out(credentials: Credentials) -> None:
    """Forget this sign-in token."""
    if credentials:
        state["sessions"].pop(credentials.credentials, None)
