"""OI analytics endpoint: PCR, max pain, buildup, delta-OI history."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..services import oi_analytics
from ..services.options_chain import build_chain

router = APIRouter(prefix="/api", tags=["oi"])


@router.get("/oi/{symbol}")
def oi_analytics_endpoint(
    symbol: str,
    expiry: str | None = Query(None),
    history_hours: int = Query(8, ge=1, le=48),
) -> dict:
    chain = build_chain(symbol, expiry, strike_window=25)
    if chain.get("error") and not chain.get("rows"):
        raise HTTPException(404, chain["error"])

    # Per-strike buildup table.
    buildup = []
    for r in chain["rows"]:
        buildup.append(
            {
                "strike": r["strike"],
                "ce": {
                    "oi": (r["ce"] or {}).get("oi"),
                    "oi_change": (r["ce"] or {}).get("oi_change"),
                    "buildup": (r["ce"] or {}).get("buildup"),
                } if r["ce"] else None,
                "pe": {
                    "oi": (r["pe"] or {}).get("oi"),
                    "oi_change": (r["pe"] or {}).get("oi_change"),
                    "buildup": (r["pe"] or {}).get("buildup"),
                } if r["pe"] else None,
            }
        )

    return {
        "symbol": symbol.upper(),
        "expiry": chain["expiry"],
        "spot": chain.get("spot"),
        "atm_strike": chain.get("atm_strike"),
        "analytics": chain["analytics"],
        "buildup": buildup,
        "oi_history": oi_analytics.oi_history(symbol, chain["expiry"], history_hours),
    }
