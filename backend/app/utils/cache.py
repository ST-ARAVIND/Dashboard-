"""Market-aware in-memory TTL cache.

Heavy computations (option chain, breadth, term structure) are recomputed far
more often than the data changes — every page poll and several UI components hit
the same underlying. This caches results with a short TTL during market hours and
a long TTL when the market is closed (the data is static then), which massively
cuts the number of rate-limited Angel calls and makes the hosted app responsive.
"""
from __future__ import annotations

import functools
import threading
import time

from .market_hours import is_market_open


def market_ttl_cache(open_ttl: float = 12.0, closed_ttl: float = 600.0):
    """Decorator: cache a function's result with a market-hours-aware TTL.

    open_ttl   — seconds to cache while the market is open (keep it fresh).
    closed_ttl — seconds to cache when closed (data is last-traded, static).
    """

    def decorator(fn):
        store: dict = {}
        lock = threading.Lock()

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            ttl = open_ttl if is_market_open() else closed_ttl
            now = time.time()
            with lock:
                hit = store.get(key)
                if hit and (now - hit[0]) < ttl:
                    return hit[1]
            # Compute outside the lock so slow Angel calls don't serialize callers
            # onto each other; last writer wins (results are equivalent).
            value = fn(*args, **kwargs)
            with lock:
                store[key] = (now, value)
            return value

        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
