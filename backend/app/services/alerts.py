"""Alert manager: evaluates user alerts against the live tick stream.

Active alerts are cached in memory keyed by token so evaluation on every tick is
a cheap dict lookup (no DB hit per tick). On create/delete/toggle the cache and
the upstream feed subscription are kept in sync. When an alert fires it is
persisted (triggered_at/value), deactivated unless ``repeat``, and the trigger is
returned so the websocket hub can broadcast it to the browser.
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime

from sqlalchemy import select

from ..models import Alert, SessionLocal

logger = logging.getLogger("services.alerts")


def _value_for(metric: str, tick: dict) -> float | None:
    if metric == "ltp":
        return tick.get("ltp")
    if metric == "oi":
        return tick.get("oi")
    if metric == "percent_change":
        ltp, close = tick.get("ltp"), tick.get("close")
        if ltp is not None and close:
            return (ltp - close) / close * 100.0
    return None


def _crossed(value: float, operator: str, threshold: float) -> bool:
    return value >= threshold if operator == "above" else value <= threshold


class AlertManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        # token -> list[alert dict] of ACTIVE alerts
        self._by_token: dict[str, list[dict]] = {}

    # ------------------------------------------------------------------ #
    def load_active(self) -> list[dict]:
        """Reload the in-memory cache from the DB. Returns tokens to subscribe."""
        with SessionLocal() as db:
            rows = db.scalars(select(Alert).where(Alert.active.is_(True))).all()
            alerts = [r.as_dict() for r in rows]
        with self._lock:
            self._by_token = {}
            for a in alerts:
                self._by_token.setdefault(a["token"], []).append(a)
        logger.info("Loaded %d active alerts across %d tokens", len(alerts), len(self._by_token))
        return alerts

    def subscribe_tokens(self) -> list[dict]:
        """Instruments the feed must subscribe so alerts can be evaluated."""
        with self._lock:
            seen: dict[str, dict] = {}
            for token, alerts in self._by_token.items():
                if alerts:
                    seen[token] = {"token": token, "exch_seg": alerts[0]["exch_seg"]}
            return list(seen.values())

    # ------------------------------------------------------------------ #
    def evaluate(self, tick: dict) -> list[dict]:
        """Check a tick against cached alerts. Returns fired alert payloads."""
        token = tick.get("token")
        if not token:
            return []
        with self._lock:
            candidates = list(self._by_token.get(token, ()))
        if not candidates:
            return []

        fired: list[dict] = []
        for a in candidates:
            val = _value_for(a["metric"], tick)
            if val is None:
                continue
            if _crossed(val, a["operator"], a["threshold"]):
                fired.append({**a, "value": round(val, 2)})

        if fired:
            self._mark_fired(fired)
        return fired

    def _mark_fired(self, fired: list[dict]) -> None:
        now = datetime.utcnow()
        with SessionLocal() as db:
            for f in fired:
                row = db.get(Alert, f["id"])
                if not row:
                    continue
                row.triggered_at = now
                row.triggered_value = f["value"]
                if not row.repeat:
                    row.active = False
            db.commit()
        # Update cache: drop one-shot alerts that just fired.
        with self._lock:
            for f in fired:
                lst = self._by_token.get(f["token"], [])
                if not f.get("repeat"):
                    self._by_token[f["token"]] = [x for x in lst if x["id"] != f["id"]]

    # ------------------------------------------------------------------ #
    # CRUD (DB + cache)
    # ------------------------------------------------------------------ #
    def create(self, data: dict) -> dict:
        with SessionLocal() as db:
            alert = Alert(
                token=str(data["token"]),
                symbol=data.get("symbol", ""),
                exch_seg=data.get("exch_seg", "NSE"),
                metric=data.get("metric", "ltp"),
                operator=data.get("operator", "above"),
                threshold=float(data["threshold"]),
                note=data.get("note", ""),
                repeat=bool(data.get("repeat", False)),
                active=True,
            )
            db.add(alert)
            db.commit()
            db.refresh(alert)
            out = alert.as_dict()
        with self._lock:
            self._by_token.setdefault(out["token"], []).append(out)
        return out

    def list_all(self) -> list[dict]:
        with SessionLocal() as db:
            rows = db.scalars(select(Alert).order_by(Alert.created_at.desc())).all()
            return [r.as_dict() for r in rows]

    def delete(self, alert_id: int) -> bool:
        with SessionLocal() as db:
            row = db.get(Alert, alert_id)
            if not row:
                return False
            token = row.token
            db.delete(row)
            db.commit()
        with self._lock:
            if token in self._by_token:
                self._by_token[token] = [x for x in self._by_token[token] if x["id"] != alert_id]
        return True

    def set_active(self, alert_id: int, active: bool) -> dict | None:
        with SessionLocal() as db:
            row = db.get(Alert, alert_id)
            if not row:
                return None
            row.active = active
            if active:
                row.triggered_at = None
                row.triggered_value = None
            db.commit()
            out = row.as_dict()
        # Rebuild cache for correctness.
        self.load_active()
        return out


alert_manager = AlertManager()
