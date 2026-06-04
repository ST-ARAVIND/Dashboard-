"""Instrument lookup endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..angel.scrip_master import scrip_master

router = APIRouter(prefix="/api", tags=["instruments"])


@router.get("/search")
def search(q: str = Query(..., min_length=1), limit: int = 20) -> dict:
    return {"query": q, "results": scrip_master.search(q, limit)}


@router.get("/instrument/{token}")
def instrument(token: str) -> dict:
    inst = scrip_master.get_by_token(token)
    if not inst:
        raise HTTPException(404, f"No instrument for token {token}")
    return inst


@router.get("/expiries")
def expiries(symbol: str = Query(...)) -> dict:
    return {"symbol": symbol.upper(), "expiries": scrip_master.list_expiries(symbol)}
