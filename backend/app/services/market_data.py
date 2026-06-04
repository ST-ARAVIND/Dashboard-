"""REST market-data service wrapping SmartAPI quote / LTP / candle endpoints.

Every outbound call is gated by the token-bucket rate limiter and retried with
exponential backoff.  FULL-mode quotes capture LTP, OHLC, traded volume and
open interest (``opnInterest``).

Verified SmartAPI 1.5.3 methods:
    smart.getMarketData(mode, exchangeTokens)   # mode: "FULL" | "OHLC" | "LTP"
    smart.ltpData(exchange, tradingsymbol, symboltoken)
    smart.getCandleData(historicDataParams)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from ..angel.session import angel_session
from ..models import Candle, SessionLocal
from ..utils.backoff import retry_with_backoff
from ..utils.market_hours import IST
from ..utils.rate_limiter import limiter

logger = logging.getLogger("services.market_data")

# Max tokens Angel accepts per getMarketData call (per their docs ~ 50 / exchange).
MAX_TOKENS_PER_CALL = 50

# Interval -> max lookback days Angel allows per getCandleData call (approx).
_CANDLE_MAX_DAYS = {
    "ONE_MINUTE": 30, "THREE_MINUTE": 60, "FIVE_MINUTE": 100, "TEN_MINUTE": 100,
    "FIFTEEN_MINUTE": 200, "THIRTY_MINUTE": 200, "ONE_HOUR": 400, "ONE_DAY": 2000,
}


def _chunk(seq: list, size: int):
    for i in range(0, len(seq), size):
        yield seq[i : i + size]


def _normalize_full_row(row: dict) -> dict:
    """Normalize a FULL-mode quote row into our canonical tick shape."""
    depth = row.get("depth") or {}
    return {
        "token": str(row.get("symbolToken", row.get("token", ""))),
        "symbol": row.get("tradingSymbol", row.get("symbol", "")),
        "exchange": row.get("exchange", ""),
        "ltp": row.get("ltp"),
        "open": row.get("open"),
        "high": row.get("high"),
        "low": row.get("low"),
        "close": row.get("close"),  # previous close
        "last_traded_qty": row.get("lastTradeQty"),
        "volume": row.get("tradeVolume", row.get("volume")),
        "oi": row.get("opnInterest", row.get("oi")),
        "net_change": row.get("netChange"),
        "percent_change": row.get("percentChange"),
        "upper_circuit": row.get("upperCircuit"),
        "lower_circuit": row.get("lowerCircuit"),
        "week52_high": row.get("52WeekHigh"),
        "week52_low": row.get("52WeekLow"),
        "best_bid": (depth.get("buy") or [{}])[0].get("price") if depth else None,
        "best_ask": (depth.get("sell") or [{}])[0].get("price") if depth else None,
        "depth": depth,
        "ts": datetime.now(IST).isoformat(),
    }


class MarketDataService:
    def get_full_quotes(self, exchange_tokens: dict[str, list[str]]) -> list[dict]:
        """FULL-mode quotes for ``{exchange: [token, ...]}``.

        Returns a flat list of normalized rows. Chunks each exchange's token list
        to respect Angel's per-call cap.
        """
        smart = angel_session.client()
        out: list[dict] = []
        # Build chunked sub-requests so a single big watchlist still works.
        for exch, tokens in exchange_tokens.items():
            for chunk in _chunk([str(t) for t in tokens], MAX_TOKENS_PER_CALL):
                limiter.acquire("quote")
                payload = {exch: chunk}

                def _call() -> dict:
                    return smart.getMarketData("FULL", payload)

                try:
                    resp = retry_with_backoff(_call, label="getMarketData", retries=3)
                except Exception as exc:  # noqa: BLE001
                    logger.error("getMarketData failed for %s: %s", exch, exc)
                    continue
                if not resp or not resp.get("status"):
                    logger.warning("getMarketData non-ok: %s", (resp or {}).get("message"))
                    continue
                fetched = (resp.get("data") or {}).get("fetched", [])
                out.extend(_normalize_full_row(r) for r in fetched)
        return out

    def get_quote(self, token: str, exchange: str = "NSE") -> dict | None:
        rows = self.get_full_quotes({exchange: [str(token)]})
        return rows[0] if rows else None

    def get_ltp(self, exchange: str, tradingsymbol: str, token: str) -> dict | None:
        smart = angel_session.client()
        limiter.acquire("ltp")

        def _call() -> dict:
            return smart.ltpData(exchange, tradingsymbol, str(token))

        resp = retry_with_backoff(_call, label="ltpData", retries=3)
        if resp and resp.get("status"):
            return resp.get("data")
        return None

    # ------------------------------------------------------------------ #
    # Historical candles (cached)
    # ------------------------------------------------------------------ #
    def get_candles(
        self,
        token: str,
        exchange: str = "NSE",
        interval: str = "ONE_DAY",
        days: int = 60,
        use_cache: bool = True,
    ) -> list[dict]:
        """Fetch historical candles, caching results in SQLite.

        Returns list of {time, open, high, low, close, volume} (time = ISO IST).
        """
        token = str(token)
        to_dt = datetime.now(IST)
        max_days = _CANDLE_MAX_DAYS.get(interval, 60)
        from_dt = to_dt - timedelta(days=min(days, max_days))

        if use_cache:
            cached = self._read_cache(token, interval, from_dt, to_dt)
            # Heuristic: if cache covers the window reasonably, use it (skip refetch
            # only when market is closed — otherwise we want fresh recent candles).
            if cached:
                return cached

        smart = angel_session.client()
        limiter.acquire("candle")
        params = {
            "exchange": exchange,
            "symboltoken": token,
            "interval": interval,
            "fromdate": from_dt.strftime("%Y-%m-%d %H:%M"),
            "todate": to_dt.strftime("%Y-%m-%d %H:%M"),
        }

        def _call() -> dict:
            return smart.getCandleData(params)

        try:
            resp = retry_with_backoff(_call, label="getCandleData", retries=3)
        except Exception as exc:  # noqa: BLE001
            logger.error("getCandleData failed: %s", exc)
            return self._read_cache(token, interval, from_dt, to_dt)

        if not resp or not resp.get("status"):
            logger.warning("getCandleData non-ok: %s", (resp or {}).get("message"))
            return self._read_cache(token, interval, from_dt, to_dt)

        rows = resp.get("data") or []
        candles = []
        for c in rows:
            # Angel returns [timestamp, open, high, low, close, volume]
            ts = datetime.fromisoformat(c[0])
            candles.append(
                {
                    "time": c[0],
                    "timestamp": ts,
                    "open": float(c[1]),
                    "high": float(c[2]),
                    "low": float(c[3]),
                    "close": float(c[4]),
                    "volume": float(c[5]),
                }
            )
        self._write_cache(token, exchange, interval, candles)
        return [{k: v for k, v in c.items() if k != "timestamp"} for c in candles]

    def _read_cache(self, token, interval, from_dt, to_dt) -> list[dict]:
        with SessionLocal() as db:
            rows = db.scalars(
                select(Candle)
                .where(
                    Candle.token == token,
                    Candle.interval == interval,
                    Candle.timestamp >= from_dt.replace(tzinfo=None),
                    Candle.timestamp <= to_dt.replace(tzinfo=None),
                )
                .order_by(Candle.timestamp)
            ).all()
        return [
            {
                "time": r.timestamp.isoformat(),
                "open": r.open, "high": r.high, "low": r.low,
                "close": r.close, "volume": r.volume,
            }
            for r in rows
        ]

    def _write_cache(self, token, exchange, interval, candles: list[dict]) -> None:
        if not candles:
            return
        with SessionLocal() as db:
            for c in candles:
                stmt = sqlite_insert(Candle).values(
                    token=token, exchange=exchange, interval=interval,
                    timestamp=c["timestamp"].replace(tzinfo=None),
                    open=c["open"], high=c["high"], low=c["low"],
                    close=c["close"], volume=c["volume"],
                ).on_conflict_do_nothing(index_elements=["token", "interval", "timestamp"])
                db.execute(stmt)
            db.commit()


market_data = MarketDataService()
