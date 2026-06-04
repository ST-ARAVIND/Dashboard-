"""Exponential backoff retry helper for SmartAPI calls."""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger("angel.backoff")

T = TypeVar("T")


def retry_with_backoff(
    fn: Callable[[], T],
    *,
    retries: int = 4,
    base_delay: float = 0.5,
    max_delay: float = 8.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    label: str = "call",
) -> T:
    """Call ``fn`` with exponential backoff on failure.

    Re-raises the last exception if all retries are exhausted.
    """
    attempt = 0
    while True:
        try:
            return fn()
        except exceptions as exc:  # noqa: BLE001 — deliberately broad, re-raised below
            attempt += 1
            if attempt > retries:
                logger.error("%s failed after %d attempts: %s", label, attempt - 1, exc)
                raise
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            logger.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.1fs",
                label, attempt, retries, exc, delay,
            )
            time.sleep(delay)
