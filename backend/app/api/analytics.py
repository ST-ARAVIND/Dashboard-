"""Cross-expiry analytics: IV term structure + multi-expiry PCR trend."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..services.options_chain import term_structure

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/term-structure")
def term_structure_endpoint(
    symbol: str = Query(..., description="Underlying, e.g. NIFTY"),
    expiries: int = Query(5, ge=1, le=8, description="number of nearest expiries"),
) -> dict:
    return term_structure(symbol, max_expiries=expiries)
