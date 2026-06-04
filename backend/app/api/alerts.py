"""Price / OI alert management."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..angel.feed import angel_feed
from ..services.alerts import alert_manager

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


class AlertIn(BaseModel):
    token: str
    symbol: str
    exch_seg: str = "NSE"
    metric: str = Field(default="ltp", pattern="^(ltp|percent_change|oi)$")
    operator: str = Field(default="above", pattern="^(above|below)$")
    threshold: float
    note: str = ""
    repeat: bool = False


@router.get("")
def list_alerts() -> dict:
    return {"alerts": alert_manager.list_all()}


@router.post("")
def create_alert(alert: AlertIn) -> dict:
    created = alert_manager.create(alert.model_dump())
    # Make sure the feed is streaming this token so the alert can evaluate.
    try:
        angel_feed.subscribe([{"token": created["token"], "exch_seg": created["exch_seg"]}])
    except Exception:  # noqa: BLE001
        pass
    return created


@router.delete("/{alert_id}")
def delete_alert(alert_id: int) -> dict:
    if not alert_manager.delete(alert_id):
        raise HTTPException(404, "Alert not found")
    return {"ok": True}


@router.post("/{alert_id}/toggle")
def toggle_alert(alert_id: int, active: bool) -> dict:
    out = alert_manager.set_active(alert_id, active)
    if not out:
        raise HTTPException(404, "Alert not found")
    if active:
        try:
            angel_feed.subscribe([{"token": out["token"], "exch_seg": out["exch_seg"]}])
        except Exception:  # noqa: BLE001
            pass
    return out
