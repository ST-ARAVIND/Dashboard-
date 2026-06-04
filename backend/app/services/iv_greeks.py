"""Implied volatility & option Greeks (computed — Angel does not return them).

Index options (NIFTY, BANKNIFTY, FINNIFTY, ...) are European and priced with
Black-Scholes via py_vollib / py_vollib_vectorized.  Stock options are American;
BS is used as an acceptable approximation (a binomial model can be swapped in).

Backend selection:
  * The pure-Python scalar ``py_vollib`` is the reliable default (scipy-based,
    no JIT) and is fast enough for on-demand chains of ~60-120 strikes.
  * ``py_vollib_vectorized`` (numba-accelerated) is used ONLY if an import-time
    self-test computes cleanly on the installed numba/numpy — older releases of
    that package fail to JIT against numpy 2.x.

Inputs per leg:
    price : option market price (LTP)
    S     : spot (underlying LTP)
    K     : strike
    t     : time to expiry in YEARS (calendar time, market-hours aware)
    r     : risk-free rate (configurable; default ~6.5%)
    flag  : 'c' for CE, 'p' for PE
"""
from __future__ import annotations

import logging
from datetime import datetime

import numpy as np

from ..config import settings
from ..utils.market_hours import IST, seconds_to_expiry

logger = logging.getLogger("services.iv_greeks")

_SECONDS_PER_YEAR = 365.0 * 24.0 * 3600.0

# --- Scalar backend (always required) ---
try:  # pragma: no cover - import guard
    from py_vollib.black_scholes.implied_volatility import implied_volatility as _bs_iv
    from py_vollib.black_scholes.greeks.analytical import (
        delta as _bs_delta,
        gamma as _bs_gamma,
        theta as _bs_theta,
        vega as _bs_vega,
        rho as _bs_rho,
    )

    _SCALAR = True
except Exception as exc:  # noqa: BLE001
    _SCALAR = False
    logger.error("py_vollib unavailable (%s); IV/Greeks disabled", exc)

# --- Optional vectorized backend (numba). Self-tested below. ---
_VECTORIZED = False
_vec = {}
try:  # pragma: no cover - import guard
    from py_vollib_vectorized import (
        vectorized_implied_volatility,
        vectorized_delta,
        vectorized_gamma,
        vectorized_theta,
        vectorized_vega,
        vectorized_rho,
    )

    # Self-test: force the numba JIT to run once; disable on any failure.
    _t = 30.0 / 365.0
    _probe = vectorized_implied_volatility(
        300.0, 24500.0, 24400.0, _t, 0.065, "c",
        q=0, model="black_scholes", return_as="numpy", on_error="ignore",
    )
    if np.isfinite(np.asarray(_probe, dtype=float)).any():
        _vec = {
            "iv": vectorized_implied_volatility,
            "delta": vectorized_delta,
            "gamma": vectorized_gamma,
            "theta": vectorized_theta,
            "vega": vectorized_vega,
            "rho": vectorized_rho,
        }
        _VECTORIZED = True
        logger.info("IV/Greeks: using py_vollib_vectorized (numba)")
except Exception as exc:  # noqa: BLE001
    logger.info("py_vollib_vectorized disabled (%s); using scalar py_vollib", exc)


def years_to_expiry(expiry_dt: datetime, now: datetime | None = None) -> float:
    """Time to expiry in years (calendar). Floored to a tiny positive value."""
    now = now or datetime.now(IST)
    secs = seconds_to_expiry(expiry_dt, now)
    return max(secs / _SECONDS_PER_YEAR, 1e-6)


def _arr(values) -> np.ndarray:
    return np.asarray(values, dtype=float)


def _scalar_chain(price, S, K, t, flag, r, valid) -> dict[str, np.ndarray]:
    """Per-leg scalar fallback using py_vollib."""
    n = len(price)
    out = {k: np.full(n, np.nan) for k in ("iv", "delta", "gamma", "theta", "vega", "rho")}
    if not _SCALAR:
        return out
    for i in range(n):
        if not valid[i]:
            continue
        f = flag[i]
        try:
            sigma = _bs_iv(float(price[i]), float(S[i]), float(K[i]), float(t[i]), r, f)
            out["iv"][i] = sigma
            out["delta"][i] = _bs_delta(f, float(S[i]), float(K[i]), float(t[i]), r, sigma)
            out["gamma"][i] = _bs_gamma(f, float(S[i]), float(K[i]), float(t[i]), r, sigma)
            out["theta"][i] = _bs_theta(f, float(S[i]), float(K[i]), float(t[i]), r, sigma)
            out["vega"][i] = _bs_vega(f, float(S[i]), float(K[i]), float(t[i]), r, sigma)
            out["rho"][i] = _bs_rho(f, float(S[i]), float(K[i]), float(t[i]), r, sigma)
        except Exception:  # noqa: BLE001 — un-invertible price (deep ITM/OTM)
            continue
    return out


def _vectorized_chain(price, S, K, t, flag, r, valid) -> dict[str, np.ndarray]:
    n = len(price)
    nan = np.full(n, np.nan)
    out = {k: nan.copy() for k in ("iv", "delta", "gamma", "theta", "vega", "rho")}
    iv_v = _vec["iv"](
        price[valid], S[valid], K[valid], t[valid], r, flag[valid],
        q=0, model="black_scholes", return_as="numpy", on_error="ignore",
    )
    out["iv"][valid] = iv_v
    ok = np.isfinite(iv_v) & (iv_v > 0)
    idx = np.where(valid)[0][ok]
    if len(idx):
        fv, Sv, Kv, tv, sg = flag[idx], S[idx], K[idx], t[idx], iv_v[ok]
        for greek in ("delta", "gamma", "theta", "vega", "rho"):
            out[greek][idx] = _vec[greek](
                fv, Sv, Kv, tv, r, sg, model="black_scholes", return_as="numpy"
            )
    return out


def compute_chain_iv_greeks(prices, spots, strikes, t_years, flags, r: float | None = None):
    """Vectorized IV + Greeks across a chain.

    All array args are equal-length sequences; ``flags`` are 'c'/'p' strings.
    Invalid/zero/expired legs produce NaN. Returns dict of numpy arrays.
    """
    r = settings.risk_free_rate if r is None else r
    price, S, K, t = _arr(prices), _arr(spots), _arr(strikes), _arr(t_years)
    flag = np.asarray([str(f).lower()[0] if f else "c" for f in flags])
    valid = (price > 0) & (S > 0) & (K > 0) & (t > 0)

    if not valid.any():
        n = len(price)
        return {k: np.full(n, np.nan) for k in ("iv", "delta", "gamma", "theta", "vega", "rho")}

    if _VECTORIZED:
        try:
            return _vectorized_chain(price, S, K, t, flag, r, valid)
        except Exception as exc:  # noqa: BLE001
            logger.warning("vectorized IV/Greeks failed (%s); using scalar", exc)
    return _scalar_chain(price, S, K, t, flag, r, valid)


def clean(value) -> float | None:
    """Convert numpy float / NaN to a JSON-safe rounded float or None."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if not np.isfinite(f):
        return None
    return round(f, 4)
