"""News + sentiment endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ..services import sentiment as svc

router = APIRouter(prefix="/api/sentiment", tags=["sentiment"])


@router.get("/market")
def market_sentiment(limit: int = 50) -> dict:
    return svc.market_feed(limit)


@router.get("/{symbol}")
def symbol_sentiment(symbol: str, limit: int = 30) -> dict:
    return svc.symbol_feed(symbol, limit)


@router.post("/refresh")
def refresh() -> dict:
    new = svc.ingest_news()
    return {"ingested": new}
