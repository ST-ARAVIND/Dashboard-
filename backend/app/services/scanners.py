"""Stock scanners: Volume Rate of Change (VROC) and Gap analysis.

Both are computed from daily candles for the F&O stock universe. Candles are
fetched via the market-data service (which caches them in SQLite), so after the
first cold run subsequent refreshes are cheap. Results are cached in memory and
refreshed by a scheduler job; the API serves the cache instantly.

  * VROC   — today's volume vs the trailing ~14-day average volume (% change).
             High VROC = unusual participation / accumulation or distribution.
  * Gap    — today's open vs yesterday's close (%), classified:
               Breakaway  — gap in the direction of the day's move (trend start)
               Exhaustion — gap against the day's move (possible reversal)
               Common     — small gap, likely to fill
"""
from __future__ import annotations

import logging
import threading

from ..angel.scrip_master import scrip_master
from ..utils.market_hours import now_ist
from .market_data import market_data

logger = logging.getLogger("services.scanners")

# Bound the universe so a cold refresh stays well under a minute on the candle
# rate limiter (subsequent runs hit the SQLite candle cache and are fast).
MAX_UNIVERSE = 120

# Sector mapping for grouping/labels (NSE F&O stocks).
SECTOR_MAP: dict[str, list[str]] = {
    "Banking": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "INDUSINDBK",
                "BANKBARODA", "PNB", "CANBK", "FEDERALBNK", "AUBANK", "BANDHANBNK",
                "YESBANK", "RBLBANK", "IDFCFIRSTB"],
    "IT": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTIM", "COFORGE", "MPHASIS",
           "PERSISTENT", "LTTS", "TATAELXSI", "NAUKRI"],
    "Pharma": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "TORNTPHARM", "LUPIN",
               "AUROPHARMA", "BIOCON", "GLENMARK", "ALKEM", "IPCALAB", "LAURUSLABS",
               "ZYDUSLIFE", "LALPATHLAB", "MAXHEALTH", "FORTIS", "APOLLOHOSP"],
    "Auto": ["TATAMOTORS", "MARUTI", "M&M", "BAJAJ-AUTO", "HEROMOTOCO", "EICHERMOT",
             "TVSMOTOR", "ASHOKLEY", "ESCORTS", "MOTHERSON", "APOLLOTYRE",
             "BALKRISIND", "MRF", "CEATLTD", "BHARATFORG"],
    "Metal": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "SAIL", "NMDC", "JINDALSTEL"],
    "FMCG": ["HINDUNILVR", "ITC", "NESTLEIND", "BRITANNIA", "TATACONSUM", "DABUR",
             "GODREJCP", "MARICO", "COLPAL", "JUBLFOOD", "DMART"],
    "Energy": ["RELIANCE", "NTPC", "POWERGRID", "ONGC", "BPCL", "COALINDIA", "TATAPOWER",
               "ADANIGREEN", "GAIL", "IOC", "PETRONET", "MGL", "IGL", "RECLTD", "PFC", "IRFC"],
    "Realty": ["DLF", "GODREJPROP", "OBEROIRLTY", "PEL"],
    "Finance": ["BAJFINANCE", "BAJAJFINSV", "SBILIFE", "HDFCLIFE", "SHRIRAMFIN",
                "LICHSGFIN", "MANAPPURAM", "MUTHOOTFIN", "CHOLAFIN"],
}
_NAME_TO_SECTOR = {n: sec for sec, names in SECTOR_MAP.items() for n in names}


def get_sector(name: str) -> str:
    return _NAME_TO_SECTOR.get(name.upper(), "Other")


def classify_gap(gap_pct: float, change_pct: float) -> str:
    if abs(gap_pct) < 0.4:
        return "None"
    same_direction = (gap_pct >= 0) == (change_pct >= 0)
    if abs(gap_pct) >= 1.5:
        return "Breakaway" if same_direction else "Exhaustion"
    return "Common"


_cache: dict = {"stocks": [], "generated_at": None}
_lock = threading.Lock()
_computing = threading.Event()
_universe_cache: list[dict] | None = None


def _universe() -> list[dict]:
    global _universe_cache
    if _universe_cache is not None:
        return _universe_cache
    names = scrip_master.fno_underlyings()
    out = []
    for n in names:
        inst = scrip_master.underlying_spot_instrument(n)
        if inst and inst["exch_seg"] == "NSE" and inst["token"]:
            out.append({"name": n, "token": inst["token"]})
    _universe_cache = out[:MAX_UNIVERSE]
    logger.info("Scanner universe: %d F&O stocks", len(_universe_cache))
    return _universe_cache


def compute() -> None:
    """(Re)compute VROC + gaps for the universe and refresh the cache."""
    if _computing.is_set():
        return
    _computing.set()
    try:
        stocks = []
        for u in _universe():
            try:
                candles = market_data.get_candles(u["token"], "NSE", "ONE_DAY", 30)
            except Exception as exc:  # noqa: BLE001
                logger.debug("candles failed for %s: %s", u["name"], exc)
                continue
            if len(candles) < 3:
                continue
            today, prev = candles[-1], candles[-2]
            prev_close = prev["close"]
            if not prev_close:
                continue
            chg = (today["close"] - prev_close) / prev_close * 100
            gap = (today["open"] - prev_close) / prev_close * 100 if today["open"] else 0.0
            prior_vols = [c["volume"] for c in candles[:-1] if c["volume"]]
            avg_vol = sum(prior_vols[-14:]) / len(prior_vols[-14:]) if prior_vols else 0
            vol = today["volume"] or 0
            vroc = ((vol / avg_vol) - 1) * 100 if avg_vol else 0.0
            vol_ratio = vol / avg_vol if avg_vol else 0.0
            stocks.append(
                {
                    "name": u["name"],
                    "sector": get_sector(u["name"]),
                    "price": round(today["close"], 2),
                    "chg": round(chg, 2),
                    "gap": round(gap, 2),
                    "gap_type": classify_gap(gap, chg),
                    "vroc": round(vroc),
                    "vol_ratio": round(vol_ratio, 2),
                    "volume": vol,
                }
            )
        with _lock:
            _cache["stocks"] = stocks
            _cache["generated_at"] = now_ist().isoformat()
        logger.info("Scanners computed for %d stocks", len(stocks))
    finally:
        _computing.clear()


def get_scanners() -> dict:
    """Return cached scanner data; kick off a background compute if empty."""
    with _lock:
        snapshot = {"stocks": list(_cache["stocks"]), "generated_at": _cache["generated_at"]}
    if not snapshot["stocks"] and not _computing.is_set():
        threading.Thread(target=compute, name="scanner-compute", daemon=True).start()
        snapshot["status"] = "computing"
    else:
        snapshot["status"] = "computing" if _computing.is_set() else "ready"
    return snapshot
