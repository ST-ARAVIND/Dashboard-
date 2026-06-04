"""Market breadth / composite sentiment gauge endpoint."""
from __future__ import annotations

from fastapi import APIRouter

from ..services.market_breadth import market_breadth

router = APIRouter(prefix="/api", tags=["breadth"])


@router.get("/breadth")
def breadth() -> dict:
    return market_breadth()
