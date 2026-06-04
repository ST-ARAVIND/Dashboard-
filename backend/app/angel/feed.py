"""Live market feed via SmartWebSocketV2.

Owns a single upstream Angel One websocket connection, manages the set of
subscribed tokens, normalizes binary ticks, and forwards them to a registered
sink (the frontend relay hub).  Auto-resubscribes on reconnect and pauses
cleanly when the market is closed.

Verified SmartAPI 1.5.3:
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2
    sws = SmartWebSocketV2(auth_token, api_key, client_code, feed_token)
    sws.subscribe(correlation_id, mode, token_list)
    callbacks: on_open / on_data / on_error / on_close
    modes: LTP=1, QUOTE=2, SNAP_QUOTE=3, DEPTH=4
    exchangeType: NSE_CM=1, NSE_FO=2, BSE_CM=3, BSE_FO=4, MCX_FO=5, CDS_FO=13
"""
from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import datetime, timezone

from ..config import settings
from .session import angel_session

logger = logging.getLogger("angel.feed")

try:  # pragma: no cover - import guard
    from SmartApi.smartWebSocketV2 import SmartWebSocketV2  # type: ignore
except Exception as _exc:  # noqa: BLE001
    SmartWebSocketV2 = None  # type: ignore
    _WS_IMPORT_ERROR = _exc
else:
    _WS_IMPORT_ERROR = None

# SmartWebSocketV2 subscription modes.
MODE_LTP = 1
MODE_QUOTE = 2
MODE_SNAP_QUOTE = 3

# exch_seg string -> SmartWebSocketV2 exchangeType int.
EXCHANGE_TYPE = {
    "NSE": 1, "NSE_CM": 1,
    "NFO": 2, "NSE_FO": 2,
    "BSE": 3, "BSE_CM": 3,
    "BFO": 4, "BSE_FO": 4,
    "MCX": 5, "MCX_FO": 5,
    "CDS": 13, "CDS_FO": 13,
}

CORRELATION_ID = "market-dashboard"


def _to_paise_price(val) -> float | None:
    """SmartWebSocketV2 ships prices * 100 (paise)."""
    if val is None:
        return None
    try:
        return round(float(val) / 100.0, 2)
    except (TypeError, ValueError):
        return None


class AngelFeed:
    """Singleton upstream websocket manager."""

    def __init__(self) -> None:
        self._sws = None
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._connected = threading.Event()
        self._sink: Callable[[dict], None] | None = None
        # token (str) -> {"exchangeType": int, "mode": int}
        self._subscriptions: dict[str, dict] = {}
        self._stopped = False

    # ------------------------------------------------------------------ #
    def set_sink(self, sink: Callable[[dict], None]) -> None:
        """Register the callback that receives every normalized tick."""
        self._sink = sink

    @property
    def is_connected(self) -> bool:
        return self._connected.is_set()

    def status(self) -> dict:
        return {
            "connected": self.is_connected,
            "subscribed_tokens": len(self._subscriptions),
        }

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Connect upstream in a background thread (idempotent)."""
        if SmartWebSocketV2 is None:
            logger.error("SmartWebSocketV2 unavailable: %s", _WS_IMPORT_ERROR)
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stopped = False
            self._thread = threading.Thread(
                target=self._run, name="angel-feed", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        self._stopped = True
        self._connected.clear()
        try:
            if self._sws:
                self._sws.close_connection()
        except Exception as exc:  # noqa: BLE001
            logger.debug("ws close error (ignored): %s", exc)

    def _run(self) -> None:
        try:
            auth_token = angel_session.jwt_token or angel_session.client() and angel_session.jwt_token
            feed_token = angel_session.get_feed_token()
        except Exception as exc:  # noqa: BLE001
            logger.error("Cannot start feed — auth failed: %s", exc)
            return

        self._sws = SmartWebSocketV2(
            auth_token,
            settings.angel_api_key,
            settings.angel_client_code,
            feed_token,
            max_retry_attempt=5,
            retry_strategy=1,      # exponential
            retry_delay=5,
            retry_multiplier=2,
            retry_duration=300,
        )

        self._sws.on_open = self._on_open
        self._sws.on_data = self._on_data
        self._sws.on_error = self._on_error
        self._sws.on_close = self._on_close

        logger.info("Connecting to Angel One live feed...")
        # connect() blocks, running the websocket loop on this thread.
        self._sws.connect()

    # ------------------------------------------------------------------ #
    # Subscription management
    # ------------------------------------------------------------------ #
    def subscribe(self, tokens: list[dict], mode: int = MODE_SNAP_QUOTE) -> None:
        """Subscribe a list of ``{"token","exch_seg"}`` dicts.

        Records the subscription so we can re-apply it on reconnect.
        """
        by_exch: dict[int, list[str]] = {}
        for t in tokens:
            token = str(t["token"])
            ex = EXCHANGE_TYPE.get(str(t.get("exch_seg", "NSE")).upper(), 1)
            self._subscriptions[token] = {"exchangeType": ex, "mode": mode}
            by_exch.setdefault(ex, []).append(token)

        if not self.is_connected or not self._sws:
            # Will be applied once connected (see _on_open).
            return
        token_list = [{"exchangeType": ex, "tokens": toks} for ex, toks in by_exch.items()]
        try:
            self._sws.subscribe(CORRELATION_ID, mode, token_list)
            logger.info("Subscribed %d tokens (mode=%d)", len(tokens), mode)
        except Exception as exc:  # noqa: BLE001
            logger.error("subscribe failed: %s", exc)

    def unsubscribe(self, tokens: list[str], mode: int = MODE_SNAP_QUOTE) -> None:
        by_exch: dict[int, list[str]] = {}
        for token in tokens:
            token = str(token)
            sub = self._subscriptions.pop(token, None)
            ex = sub["exchangeType"] if sub else 1
            by_exch.setdefault(ex, []).append(token)
        if not self.is_connected or not self._sws:
            return
        token_list = [{"exchangeType": ex, "tokens": toks} for ex, toks in by_exch.items()]
        try:
            self._sws.unsubscribe(CORRELATION_ID, mode, token_list)
        except Exception as exc:  # noqa: BLE001
            logger.error("unsubscribe failed: %s", exc)

    def _resubscribe_all(self) -> None:
        if not self._subscriptions:
            return
        # Group by (mode, exchangeType).
        grouped: dict[tuple[int, int], list[str]] = {}
        for token, meta in self._subscriptions.items():
            grouped.setdefault((meta["mode"], meta["exchangeType"]), []).append(token)
        for (mode, ex), toks in grouped.items():
            try:
                self._sws.subscribe(CORRELATION_ID, mode, [{"exchangeType": ex, "tokens": toks}])
            except Exception as exc:  # noqa: BLE001
                logger.error("resubscribe failed: %s", exc)
        logger.info("Re-subscribed %d tokens after reconnect", len(self._subscriptions))

    # ------------------------------------------------------------------ #
    # Callbacks (run on the websocket thread)
    # ------------------------------------------------------------------ #
    # NOTE: the underlying websocket-client lib invokes these with a varying
    # number of positional args depending on version (e.g. on_close may be
    # called as on_close(ws, status_code, msg)). We accept *args/**kwargs so a
    # signature mismatch never raises "takes N positional arguments…" on the
    # websocket thread (which previously spammed errors on every reconnect).
    def _on_open(self, *args, **kwargs) -> None:  # noqa: ANN002
        logger.info("Angel feed connected")
        self._connected.set()
        self._resubscribe_all()

    def _on_close(self, *args, **kwargs) -> None:  # noqa: ANN002
        logger.warning("Angel feed closed")
        self._connected.clear()

    def _on_error(self, *args, **kwargs) -> None:  # noqa: ANN002
        # First non-self arg is usually the error/message; be defensive.
        error = args[1] if len(args) > 1 else (args[0] if args else kwargs)
        logger.error("Angel feed error: %s", error)

    def _on_data(self, wsapp, message, *args, **kwargs) -> None:  # noqa: ANN001,ANN002
        try:
            tick = self._normalize(message)
            if tick and self._sink:
                self._sink(tick)
        except Exception as exc:  # noqa: BLE001
            logger.debug("tick normalize error: %s", exc)

    @staticmethod
    def _normalize(m: dict) -> dict | None:
        """Normalize a SmartWebSocketV2 parsed tick into our canonical shape."""
        if not isinstance(m, dict) or "token" not in m:
            return None
        ts_ms = m.get("exchange_timestamp")
        ts_iso = None
        if ts_ms:
            try:
                ts_iso = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).isoformat()
            except Exception:  # noqa: BLE001
                ts_iso = None
        return {
            "type": "tick",
            "token": str(m.get("token")),
            "exchange_type": m.get("exchange_type"),
            "ltp": _to_paise_price(m.get("last_traded_price")),
            "open": _to_paise_price(m.get("open_price_of_the_day")),
            "high": _to_paise_price(m.get("high_price_of_the_day")),
            "low": _to_paise_price(m.get("low_price_of_the_day")),
            "close": _to_paise_price(m.get("closed_price")),
            "volume": m.get("volume_trade_for_the_day"),
            "oi": m.get("open_interest"),
            "oi_change_pct": m.get("open_interest_change_percentage"),
            "last_traded_qty": m.get("last_traded_quantity"),
            "avg_price": _to_paise_price(m.get("average_traded_price")),
            "total_buy_qty": m.get("total_buy_quantity"),
            "total_sell_qty": m.get("total_sell_quantity"),
            "ts": ts_iso,
        }


angel_feed = AngelFeed()
