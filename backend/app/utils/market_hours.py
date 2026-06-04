"""Indian market (NSE) trading-hours and holiday helpers — all in IST."""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))

MARKET_OPEN = time(9, 15)
MARKET_CLOSE = time(15, 30)

# NSE trading holidays. Update yearly; kept here so polling pauses on holidays.
# Source: NSE holiday calendar. (Add new years as needed.)
NSE_HOLIDAYS_2025 = {
    "2025-02-26", "2025-03-14", "2025-03-31", "2025-04-10", "2025-04-14",
    "2025-04-18", "2025-05-01", "2025-08-15", "2025-08-27", "2025-10-02",
    "2025-10-21", "2025-10-22", "2025-11-05", "2025-12-25",
}
NSE_HOLIDAYS_2026 = {
    "2026-01-26", "2026-03-04", "2026-03-21", "2026-03-31", "2026-04-01",
    "2026-04-14", "2026-05-01", "2026-08-15", "2026-10-02", "2026-11-09",
    "2026-12-25",
}
NSE_HOLIDAYS = NSE_HOLIDAYS_2025 | NSE_HOLIDAYS_2026


def now_ist() -> datetime:
    """Current time in IST."""
    return datetime.now(IST)


def is_trading_holiday(dt: datetime | None = None) -> bool:
    dt = dt or now_ist()
    return dt.strftime("%Y-%m-%d") in NSE_HOLIDAYS


def is_weekend(dt: datetime | None = None) -> bool:
    dt = dt or now_ist()
    return dt.weekday() >= 5  # 5 = Sat, 6 = Sun


def is_market_open(dt: datetime | None = None) -> bool:
    """True iff NSE equity/F&O market is currently open."""
    dt = dt or now_ist()
    if is_weekend(dt) or is_trading_holiday(dt):
        return False
    return MARKET_OPEN <= dt.timetz().replace(tzinfo=None) <= MARKET_CLOSE


def market_state(dt: datetime | None = None) -> dict:
    """Structured market-state object for the frontend."""
    dt = dt or now_ist()
    open_now = is_market_open(dt)
    if open_now:
        status = "open"
    elif is_weekend(dt):
        status = "weekend"
    elif is_trading_holiday(dt):
        status = "holiday"
    elif dt.timetz().replace(tzinfo=None) < MARKET_OPEN:
        status = "pre_open"
    else:
        status = "closed"
    return {
        "is_open": open_now,
        "status": status,
        "server_time_ist": dt.isoformat(),
        "open_time": MARKET_OPEN.strftime("%H:%M"),
        "close_time": MARKET_CLOSE.strftime("%H:%M"),
    }


def seconds_to_expiry(expiry_dt: datetime, now: datetime | None = None) -> float:
    """Seconds from ``now`` to an expiry datetime (both treated in IST)."""
    now = now or now_ist()
    if expiry_dt.tzinfo is None:
        expiry_dt = expiry_dt.replace(tzinfo=IST)
    return max((expiry_dt - now).total_seconds(), 0.0)
