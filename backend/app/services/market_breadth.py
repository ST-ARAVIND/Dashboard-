"""Market breadth & composite sentiment.

  * India VIX level + change (volatility index).
  * Advance/decline computed from a representative large-cap basket (Angel has no
    direct A/D endpoint, so we sample constituents and count up vs down).
  * A composite 0-100 "sentiment gauge" blending VIX, PCR and advance/decline.
"""
from __future__ import annotations

import logging

from ..angel.scrip_master import scrip_master
from ..utils.cache import market_ttl_cache
from .market_data import market_data
from .oi_analytics import pcr_sentiment

logger = logging.getLogger("services.market_breadth")

# Representative large-cap basket for an advance/decline read (kept small to
# respect rate limits). These resolve to NSE EQ tokens via the scrip master.
BREADTH_BASKET = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "INFY", "TCS", "ITC", "LT", "SBIN",
    "AXISBANK", "KOTAKBANK", "BHARTIARTL", "HINDUNILVR", "BAJFINANCE", "MARUTI",
    "ASIANPAINT", "TITAN", "SUNPHARMA", "TATAMOTORS", "WIPRO", "ONGC",
]

INDEX_TOKENS = {
    # name -> (symbol fragment used to resolve)
    "NIFTY": "NIFTY",
    "BANKNIFTY": "BANKNIFTY",
}


def india_vix() -> dict | None:
    """India VIX level + net/percent change."""
    inst = scrip_master.resolve("India VIX", "NSE") or _find_vix()
    if not inst:
        return None
    q = market_data.get_quote(inst["token"], "NSE")
    if not q:
        return None
    return {
        "value": q.get("ltp"),
        "net_change": q.get("net_change"),
        "percent_change": q.get("percent_change"),
        "prev_close": q.get("close"),
    }


def _find_vix() -> dict | None:
    for cand in scrip_master.search("VIX", limit=10):
        if "VIX" in cand["symbol"].upper() and cand["exch_seg"] == "NSE":
            return cand
    return None


def advance_decline() -> dict:
    """Count advancing vs declining names in the basket."""
    resolved = []
    for name in BREADTH_BASKET:
        inst = scrip_master.underlying_spot_instrument(name)
        if inst:
            resolved.append(inst)
    if not resolved:
        return {"advances": 0, "declines": 0, "unchanged": 0, "ratio": None, "sampled": 0}

    quotes = market_data.get_full_quotes({"NSE": [r["token"] for r in resolved]})
    adv = dec = unch = 0
    for q in quotes:
        nc = q.get("net_change")
        if nc is None:
            ltp, prev = q.get("ltp"), q.get("close")
            nc = (ltp - prev) if (ltp is not None and prev) else 0
        if nc > 0:
            adv += 1
        elif nc < 0:
            dec += 1
        else:
            unch += 1
    ratio = round(adv / dec, 3) if dec else (float(adv) if adv else None)
    return {
        "advances": adv, "declines": dec, "unchanged": unch,
        "ratio": ratio, "sampled": len(quotes),
    }


def composite_gauge(vix: dict | None, ad: dict, pcr_oi: float | None) -> dict:
    """Blend signals into a 0-100 bullishness score (50 = neutral)."""
    score = 50.0
    components = {}

    # Advance/decline: scale ratio around 1.0.
    if ad.get("advances") is not None and (ad.get("advances") or ad.get("declines")):
        total = ad["advances"] + ad["declines"] or 1
        ad_score = (ad["advances"] / total) * 100  # 0..100
        components["advance_decline"] = round(ad_score, 1)
        score += (ad_score - 50) * 0.5

    # PCR: bullish > 1.0.
    if pcr_oi is not None:
        pcr_score = max(0, min(100, 50 + (pcr_oi - 1.0) * 50))
        components["pcr"] = round(pcr_score, 1)
        score += (pcr_score - 50) * 0.3

    # VIX: high VIX = fear (bearish). ~11 calm, ~20+ fearful.
    if vix and vix.get("value"):
        v = vix["value"]
        vix_score = max(0, min(100, 100 - (v - 11) * 5))  # 11->100, 31->0
        components["vix"] = round(vix_score, 1)
        score += (vix_score - 50) * 0.2

    score = max(0, min(100, score))
    if score >= 60:
        label = "bullish"
    elif score <= 40:
        label = "bearish"
    else:
        label = "neutral"
    return {"score": round(score, 1), "label": label, "components": components}


@market_ttl_cache(open_ttl=20.0, closed_ttl=600.0)
def market_breadth() -> dict:
    vix = india_vix()
    ad = advance_decline()
    # Use NIFTY near-expiry PCR as the options sentiment input.
    pcr_oi = None
    try:
        from .options_chain import build_chain

        chain = build_chain("NIFTY", strike_window=20)
        if not chain.get("error"):
            pcr_oi = chain["analytics"].get("pcr_oi")
    except Exception as exc:  # noqa: BLE001
        logger.debug("breadth PCR fetch failed: %s", exc)

    gauge = composite_gauge(vix, ad, pcr_oi)
    return {
        "india_vix": vix,
        "advance_decline": ad,
        "pcr_oi": pcr_oi,
        "pcr_sentiment": pcr_sentiment(pcr_oi),
        "gauge": gauge,
    }
