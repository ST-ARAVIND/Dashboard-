"""Option-chain assembly.

Angel One has no single option-chain endpoint, so we build one:
  1. From the scrip master, list all CE/PE strikes for underlying + expiry.
  2. Get the underlying spot LTP.
  3. Batch FULL-mode quotes for the option tokens (LTP, volume, OI).
  4. Compute IV + Greeks (vectorized) per leg.
  5. Assemble a strike table centred on ATM, with PCR / max-pain / buildup.
  6. Expose the visible strike tokens so the caller can live-subscribe them.
"""
from __future__ import annotations

import logging

import numpy as np

from ..angel.scrip_master import parse_expiry, scrip_master
from . import iv_greeks as ivg
from . import oi_analytics as oi
from .market_data import market_data

logger = logging.getLogger("services.options_chain")


def _atm_strike(spot: float, strikes: list[float]) -> float | None:
    if not strikes or not spot:
        return None
    return min(strikes, key=lambda k: abs(k - spot))


def build_chain(
    underlying: str,
    expiry: str | None = None,
    strike_window: int = 15,
) -> dict:
    """Build the assembled option chain for ``underlying`` and ``expiry``.

    strike_window: number of strikes to keep on each side of ATM.
    """
    underlying = underlying.strip().upper()

    # Resolve expiry (default = nearest).
    expiries = scrip_master.list_expiries(underlying)
    if not expiries:
        return {"error": f"No option instruments found for {underlying}", "underlying": underlying}
    if not expiry:
        expiry = expiries[0]
    elif expiry not in expiries:
        return {"error": f"Expiry {expiry} not listed for {underlying}", "expiries": expiries}

    universe = scrip_master.option_universe(underlying, expiry)
    if not universe:
        return {"error": "Empty option universe", "underlying": underlying, "expiry": expiry}

    # Spot.
    spot_inst = scrip_master.underlying_spot_instrument(underlying)
    spot_ltp = None
    if spot_inst:
        q = market_data.get_quote(spot_inst["token"], spot_inst["exch_seg"])
        spot_ltp = (q or {}).get("ltp")

    # Batch quotes for all option tokens (NFO).
    tokens = [u["token"] for u in universe]
    quotes = market_data.get_full_quotes({"NFO": tokens})
    qmap = {q["token"]: q for q in quotes}

    # Group by strike.
    expiry_dt = parse_expiry(expiry)
    t_years = ivg.years_to_expiry(expiry_dt) if expiry_dt else 1e-6

    # Build per-leg arrays for vectorized IV/Greeks.
    legs = []  # (strike, opt_type, token, quote)
    for u in universe:
        q = qmap.get(u["token"], {})
        legs.append((u["strike"], u["option_type"], u["token"], q, u.get("lotsize", 0)))

    prices = [(_l[3].get("ltp") or 0) for _l in legs]
    spots = [spot_ltp or 0] * len(legs)
    strikes_arr = [_l[0] for _l in legs]
    flags = ["c" if _l[1] == "CE" else "p" for _l in legs]
    greeks = ivg.compute_chain_iv_greeks(prices, spots, strikes_arr, [t_years] * len(legs), flags)

    # Assemble strike rows.
    rows_by_strike: dict[float, dict] = {}
    for i, (strike, opt_type, token, q, lot) in enumerate(legs):
        row = rows_by_strike.setdefault(strike, {"strike": strike, "ce": None, "pe": None})
        delta_oi = oi.latest_oi_change(token)
        net_change = q.get("net_change")
        leg = {
            "token": token,
            "ltp": q.get("ltp"),
            "oi": q.get("oi"),
            "oi_change": delta_oi,
            "volume": q.get("volume"),
            "iv": ivg.clean(greeks["iv"][i] * 100) if np.isfinite(greeks["iv"][i]) else None,
            "delta": ivg.clean(greeks["delta"][i]),
            "gamma": ivg.clean(greeks["gamma"][i]),
            "theta": ivg.clean(greeks["theta"][i]),
            "vega": ivg.clean(greeks["vega"][i]),
            "rho": ivg.clean(greeks["rho"][i]),
            "net_change": net_change,
            "buildup": oi.classify_buildup(net_change, delta_oi),
            "lotsize": lot,
        }
        row["ce" if opt_type == "CE" else "pe"] = leg

    all_strikes = sorted(rows_by_strike.keys())
    atm = _atm_strike(spot_ltp, all_strikes) if spot_ltp else None

    # Window around ATM.
    windowed = all_strikes
    if atm is not None and strike_window:
        atm_idx = all_strikes.index(atm)
        lo = max(0, atm_idx - strike_window)
        hi = min(len(all_strikes), atm_idx + strike_window + 1)
        windowed = all_strikes[lo:hi]

    chain_rows = [rows_by_strike[s] for s in windowed]

    # Analytics over the windowed chain.
    pcr = oi.put_call_ratio(chain_rows)
    mp = oi.max_pain([rows_by_strike[s] for s in all_strikes])  # max pain over full chain
    metrics = oi.option_metrics(chain_rows, spot_ltp, atm)

    # Tokens of visible strikes for live subscription.
    visible_tokens = []
    for r in chain_rows:
        for side in ("ce", "pe"):
            if r[side]:
                visible_tokens.append({"token": r[side]["token"], "exch_seg": "NFO"})

    return {
        "underlying": underlying,
        "expiry": expiry,
        "expiries": expiries,
        "spot": spot_ltp,
        "atm_strike": atm,
        "time_to_expiry_years": round(t_years, 6),
        "rows": chain_rows,
        "analytics": {
            **pcr,
            **metrics,
            "max_pain": mp,
            "sentiment": oi.pcr_sentiment(pcr.get("pcr_oi")),
        },
        "subscribe_tokens": visible_tokens,
    }


def term_structure(underlying: str, max_expiries: int = 5) -> dict:
    """ATM implied volatility and PCR(OI) across the nearest expiries.

    Powers the IV term-structure curve and the multi-expiry PCR trend. Uses a
    tiny strike window per expiry to stay light on the quote rate limiter.
    """
    underlying = underlying.strip().upper()
    expiries = scrip_master.list_expiries(underlying)[:max_expiries]
    points = []
    for ex in expiries:
        chain = build_chain(underlying, ex, strike_window=2)
        if chain.get("error"):
            continue
        atm = chain.get("atm_strike")
        atm_row = next((r for r in chain["rows"] if r["strike"] == atm), None)
        ce_iv = (atm_row or {}).get("ce", {}) and (atm_row["ce"] or {}).get("iv")
        pe_iv = (atm_row or {}).get("pe", {}) and (atm_row["pe"] or {}).get("iv")
        ivs = [v for v in (ce_iv, pe_iv) if v is not None]
        points.append(
            {
                "expiry": ex,
                "atm_strike": atm,
                "ce_iv": ce_iv,
                "pe_iv": pe_iv,
                "atm_iv": round(sum(ivs) / len(ivs), 2) if ivs else None,
                "pcr_oi": chain["analytics"].get("pcr_oi"),
                "spot": chain.get("spot"),
            }
        )
    return {"underlying": underlying, "points": points}


def snapshot_rows_for_underlying(underlying: str, expiry: str | None = None) -> list[dict]:
    """Build the flat OI-snapshot rows for the scheduler to persist."""
    chain = build_chain(underlying, expiry, strike_window=25)
    if chain.get("error"):
        return []
    out = []
    for r in chain["rows"]:
        for side, ot in (("ce", "CE"), ("pe", "PE")):
            leg = r.get(side)
            if not leg:
                continue
            out.append(
                {
                    "token": leg["token"],
                    "underlying": underlying.upper(),
                    "expiry": chain["expiry"],
                    "strike": r["strike"],
                    "option_type": ot,
                    "ltp": leg.get("ltp") or 0,
                    "oi": leg.get("oi") or 0,
                    "volume": leg.get("volume") or 0,
                }
            )
    return out
