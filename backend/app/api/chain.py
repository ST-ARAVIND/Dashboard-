"""Assembled option-chain endpoint (IV/Greeks/OI analytics included)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services.options_chain import build_chain

router = APIRouter(prefix="/api", tags=["chain"])


@router.get("/chain")
def chain(
    symbol: str = Query(..., description="Underlying, e.g. NIFTY / BANKNIFTY / RELIANCE"),
    expiry: str | None = Query(None, description="e.g. 26JUN2025; default = nearest"),
    strikes: int = Query(15, ge=1, le=50, description="strikes each side of ATM"),
) -> dict:
    result = build_chain(symbol, expiry, strike_window=strikes)
    if result.get("error") and not result.get("rows"):
        raise HTTPException(404, result["error"])
    return result
