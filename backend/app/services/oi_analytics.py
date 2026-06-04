"""Open-interest analytics: PCR, max pain, OI buildup, change-in-OI history.

These are pure functions over an assembled option chain (list of strike rows)
plus the OISnapshot history table, so they are easy to unit test.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from ..models import OISnapshot, SessionLocal


# ---------------------------------------------------------------------- #
# PCR
# ---------------------------------------------------------------------- #
def put_call_ratio(chain_rows: list[dict]) -> dict:
    """PCR by OI and by volume across the chain.

    Each row: {"strike", "ce": {...}, "pe": {...}} where ce/pe carry oi/volume.
    """
    ce_oi = sum((r.get("ce") or {}).get("oi") or 0 for r in chain_rows)
    pe_oi = sum((r.get("pe") or {}).get("oi") or 0 for r in chain_rows)
    ce_vol = sum((r.get("ce") or {}).get("volume") or 0 for r in chain_rows)
    pe_vol = sum((r.get("pe") or {}).get("volume") or 0 for r in chain_rows)
    return {
        "pcr_oi": round(pe_oi / ce_oi, 3) if ce_oi else None,
        "pcr_volume": round(pe_vol / ce_vol, 3) if ce_vol else None,
        "total_ce_oi": ce_oi,
        "total_pe_oi": pe_oi,
    }


def pcr_sentiment(pcr_oi: float | None) -> str:
    """Crude PCR read used by the composite sentiment gauge."""
    if pcr_oi is None:
        return "neutral"
    if pcr_oi >= 1.3:
        return "bullish"      # heavy put writing
    if pcr_oi <= 0.7:
        return "bearish"      # heavy call writing
    return "neutral"


# ---------------------------------------------------------------------- #
# Option metrics (ATM IV, skew, straddle, expected move)
# ---------------------------------------------------------------------- #
def option_metrics(chain_rows: list[dict], spot: float | None, atm_strike: float | None) -> dict:
    """Derive ATM IV, IV skew, ATM straddle price and expected move.

    All from the assembled chain (CE/PE iv + ltp per strike):
      * atm_iv       — mean of ATM call & put IV (%)
      * iv_skew      — mean OTM-put IV minus mean OTM-call IV (%); >0 = put skew
      * atm_straddle — ATM call price + ATM put price (₹)
      * expected_move_pts/pct — ~1σ move to expiry ≈ the ATM straddle
    """
    out = {
        "atm_iv": None,
        "iv_skew": None,
        "atm_straddle": None,
        "expected_move_pts": None,
        "expected_move_pct": None,
    }
    if not chain_rows or atm_strike is None:
        return out

    atm = next((r for r in chain_rows if r.get("strike") == atm_strike), None)
    if atm:
        ce_iv = (atm.get("ce") or {}).get("iv")
        pe_iv = (atm.get("pe") or {}).get("iv")
        ivs = [v for v in (ce_iv, pe_iv) if v is not None]
        if ivs:
            out["atm_iv"] = round(sum(ivs) / len(ivs), 2)
        ce_ltp = (atm.get("ce") or {}).get("ltp")
        pe_ltp = (atm.get("pe") or {}).get("ltp")
        if ce_ltp is not None and pe_ltp is not None:
            straddle = ce_ltp + pe_ltp
            out["atm_straddle"] = round(straddle, 2)
            out["expected_move_pts"] = round(straddle, 2)
            if spot:
                out["expected_move_pct"] = round(straddle / spot * 100, 2)

    # Skew: OTM puts (strikes below spot) vs OTM calls (strikes above spot),
    # nearest 3 each side.
    if spot:
        below = sorted([r for r in chain_rows if r["strike"] < spot], key=lambda r: -r["strike"])[:3]
        above = sorted([r for r in chain_rows if r["strike"] > spot], key=lambda r: r["strike"])[:3]
        put_ivs = [(r.get("pe") or {}).get("iv") for r in below]
        put_ivs = [v for v in put_ivs if v is not None]
        call_ivs = [(r.get("ce") or {}).get("iv") for r in above]
        call_ivs = [v for v in call_ivs if v is not None]
        if put_ivs and call_ivs:
            out["iv_skew"] = round(sum(put_ivs) / len(put_ivs) - sum(call_ivs) / len(call_ivs), 2)
    return out


# ---------------------------------------------------------------------- #
# Max pain
# ---------------------------------------------------------------------- #
def max_pain(chain_rows: list[dict]) -> float | None:
    """Strike at which total option-writer payout is minimized (max pain)."""
    strikes = sorted({r["strike"] for r in chain_rows if r.get("strike")})
    if not strikes:
        return None
    ce_oi = {r["strike"]: (r.get("ce") or {}).get("oi") or 0 for r in chain_rows}
    pe_oi = {r["strike"]: (r.get("pe") or {}).get("oi") or 0 for r in chain_rows}

    best_strike, best_loss = None, None
    for expiry_price in strikes:
        total = 0.0
        for k in strikes:
            # CE writers lose when price > strike; PE writers lose when price < strike.
            total += ce_oi.get(k, 0) * max(expiry_price - k, 0)
            total += pe_oi.get(k, 0) * max(k - expiry_price, 0)
        if best_loss is None or total < best_loss:
            best_loss, best_strike = total, expiry_price
    return best_strike


# ---------------------------------------------------------------------- #
# OI buildup classification
# ---------------------------------------------------------------------- #
def classify_buildup(price_change: float | None, oi_change: float | None) -> str:
    """Classify a leg from price-vs-OI change.

    price up + OI up   -> Long Buildup
    price down + OI up -> Short Buildup
    price down + OI dn -> Long Unwinding
    price up + OI dn   -> Short Covering
    """
    if price_change is None or oi_change is None or (price_change == 0 and oi_change == 0):
        return "neutral"
    if oi_change > 0:
        return "long_buildup" if price_change >= 0 else "short_buildup"
    return "short_covering" if price_change >= 0 else "long_unwinding"


# ---------------------------------------------------------------------- #
# Change-in-OI history (from snapshots)
# ---------------------------------------------------------------------- #
def record_snapshots(rows: list[dict]) -> int:
    """Persist OI snapshots for delta-OI / OI-trend charts.

    rows: [{"token","underlying","expiry","strike","option_type","ltp","oi","volume"}]
    """
    if not rows:
        return 0
    now = datetime.utcnow()
    with SessionLocal() as db:
        for r in rows:
            db.add(
                OISnapshot(
                    token=str(r.get("token", "")),
                    underlying=r.get("underlying", ""),
                    expiry=r.get("expiry", ""),
                    strike=float(r.get("strike") or 0),
                    option_type=r.get("option_type", ""),
                    ltp=float(r.get("ltp") or 0),
                    oi=float(r.get("oi") or 0),
                    volume=float(r.get("volume") or 0),
                    timestamp=now,
                )
            )
        db.commit()
    return len(rows)


def oi_history(underlying: str, expiry: str, hours: int = 8) -> list[dict]:
    """Aggregate snapshot history into a time series of total CE/PE OI."""
    since = datetime.utcnow() - timedelta(hours=hours)
    with SessionLocal() as db:
        rows = db.scalars(
            select(OISnapshot)
            .where(
                OISnapshot.underlying == underlying.upper(),
                OISnapshot.expiry == expiry,
                OISnapshot.timestamp >= since,
            )
            .order_by(OISnapshot.timestamp)
        ).all()

    buckets: dict[str, dict] = {}
    for r in rows:
        key = r.timestamp.replace(second=0, microsecond=0).isoformat()
        b = buckets.setdefault(key, {"time": key, "ce_oi": 0.0, "pe_oi": 0.0})
        if r.option_type == "CE":
            b["ce_oi"] += r.oi
        elif r.option_type == "PE":
            b["pe_oi"] += r.oi
    series = sorted(buckets.values(), key=lambda x: x["time"])
    for b in series:
        b["pcr_oi"] = round(b["pe_oi"] / b["ce_oi"], 3) if b["ce_oi"] else None
    return series


def latest_oi_change(token: str) -> float | None:
    """Change in OI for a token vs its earliest snapshot today (contracts)."""
    today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as db:
        rows = db.scalars(
            select(OISnapshot)
            .where(OISnapshot.token == str(token), OISnapshot.timestamp >= today)
            .order_by(OISnapshot.timestamp)
        ).all()
    if len(rows) < 2:
        return None
    return rows[-1].oi - rows[0].oi
