"""Auth/session status endpoints. Never exposes tokens or credentials."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..angel.session import AngelAuthError, angel_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/status")
def auth_status() -> dict:
    return angel_session.status()


@router.post("/login")
def login() -> dict:
    """Force a fresh Angel One login (generates a new TOTP)."""
    try:
        return angel_session.login()
    except AngelAuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


@router.post("/logout")
def logout() -> dict:
    angel_session.logout()
    return {"ok": True}
