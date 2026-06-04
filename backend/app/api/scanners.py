"""VROC + Gap scanner endpoints (served from cache; refreshed by scheduler)."""
from __future__ import annotations

from fastapi import APIRouter

from ..services.scanners import get_scanners

router = APIRouter(prefix="/api/scanners", tags=["scanners"])


@router.get("")
def scanners() -> dict:
    """All scanned F&O stocks with VROC, gap, change, sector.

    Returns ``status: computing`` while the first/refresh pass runs (the
    frontend polls). The frontend derives the VROC leaderboard and gap views.
    """
    return get_scanners()
