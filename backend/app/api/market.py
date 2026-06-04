"""Quote, candle and market-state endpoints."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from ..angel.scrip_master import scrip_master
from ..services.market_data import market_data
from ..utils.market_hours import market_state

router = APIRouter(prefix="/api", tags=["market"])


@router.get("/market-state")
def get_market_state() -> dict:
    return market_state()


@router.get("/quote/{token}")
def quote(token: str, exchange: str = "NSE") -> dict:
    inst = scrip_master.get_by_token(token)
    if inst:
        exchange = inst["exch_seg"]
    q = market_data.get_quote(token, exchange)
    if not q:
        raise HTTPException(404, f"No quote for token {token}")
    if inst:
        q["instrument"] = inst
    return q


@router.get("/candles/{token}")
def candles(
    token: str,
    interval: str = Query("ONE_DAY"),
    days: int = Query(60, ge=1, le=2000),
    exchange: str = "NSE",
) -> dict:
    inst = scrip_master.get_by_token(token)
    if inst:
        exchange = inst["exch_seg"]
    data = market_data.get_candles(token, exchange, interval, days)
    return {"token": token, "interval": interval, "candles": data}
