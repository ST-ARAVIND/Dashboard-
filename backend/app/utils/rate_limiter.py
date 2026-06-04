"""Token-bucket rate limiter respecting Angel One's per-endpoint limits.

Angel One publishes per-second / per-minute limits per endpoint.  We model each
endpoint as an independent token bucket and gate every SmartAPI call through it.
The limiter is thread-safe (the SmartConnect SDK and websocket run on their own
threads) and exposes both blocking and async acquire paths.
"""
from __future__ import annotations

import asyncio
import threading
import time as _time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """A classic token bucket.

    rate: tokens added per second.
    capacity: max tokens (burst size).
    """

    rate: float
    capacity: float
    _tokens: float = field(init=False)
    _last: float = field(init=False)
    _lock: threading.Lock = field(init=False, default_factory=threading.Lock)

    def __post_init__(self) -> None:
        self._tokens = self.capacity
        self._last = _time.monotonic()

    def _refill(self) -> None:
        now = _time.monotonic()
        elapsed = now - self._last
        self._tokens = min(self.capacity, self._tokens + elapsed * self.rate)
        self._last = now

    def acquire(self, tokens: float = 1.0, timeout: float | None = None) -> bool:
        """Block until ``tokens`` are available (or timeout). Returns success."""
        deadline = None if timeout is None else _time.monotonic() + timeout
        while True:
            with self._lock:
                self._refill()
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return True
                needed = tokens - self._tokens
                wait = needed / self.rate
            if deadline is not None and _time.monotonic() + wait > deadline:
                return False
            _time.sleep(min(wait, 0.25))


# Angel One published limits (conservative; tune as docs change).
# Format: endpoint_key -> (per_second, per_minute)
_LIMITS: dict[str, tuple[float, float]] = {
    "ltp": (10, 500),
    "quote": (1, 60),        # market/v1/quote (FULL/OHLC) — conservative 1/s
    "candle": (3, 180),
    "search": (1, 60),
    "default": (5, 200),
}


class RateLimiterRegistry:
    """Holds one TokenBucket per endpoint key."""

    def __init__(self) -> None:
        self._buckets: dict[str, TokenBucket] = {}
        self._lock = threading.Lock()

    def _bucket(self, key: str) -> TokenBucket:
        with self._lock:
            if key not in self._buckets:
                per_sec, _per_min = _LIMITS.get(key, _LIMITS["default"])
                # Capacity = per-second rate (allow a tiny burst of 1s worth).
                self._buckets[key] = TokenBucket(rate=per_sec, capacity=max(per_sec, 1))
            return self._buckets[key]

    def acquire(self, key: str, timeout: float | None = 30.0) -> bool:
        return self._bucket(key).acquire(timeout=timeout)

    async def acquire_async(self, key: str, timeout: float | None = 30.0) -> bool:
        # Run the blocking acquire in a worker thread so we never stall the loop.
        return await asyncio.to_thread(self._bucket(key).acquire, 1.0, timeout)


limiter = RateLimiterRegistry()
