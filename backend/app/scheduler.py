"""Scheduled background jobs (APScheduler).

  * OI snapshots for tracked underlyings every N seconds during market hours.
  * News ingestion every few minutes.
  * Daily scrip-master refresh.

All jobs no-op gracefully when the market is closed or Angel auth is missing.
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .utils.market_hours import is_market_open

logger = logging.getLogger("scheduler")

# Underlyings we snapshot OI for (delta-OI / OI-trend charts).
TRACKED_UNDERLYINGS = ["NIFTY", "BANKNIFTY", "FINNIFTY"]

_scheduler: BackgroundScheduler | None = None


def _snapshot_oi_job() -> None:
    if not is_market_open() or not settings.angel_credentials_present:
        return
    from .services import oi_analytics
    from .services.options_chain import snapshot_rows_for_underlying

    total = 0
    for sym in TRACKED_UNDERLYINGS:
        try:
            rows = snapshot_rows_for_underlying(sym)
            total += oi_analytics.record_snapshots(rows)
        except Exception as exc:  # noqa: BLE001
            logger.warning("OI snapshot failed for %s: %s", sym, exc)
    if total:
        logger.info("OI snapshot wrote %d rows", total)


def _feed_manager_job() -> None:
    """Keep the live feed running during market hours, stopped outside them."""
    if not settings.angel_credentials_present:
        return
    from .angel.feed import angel_feed

    open_now = is_market_open()
    if open_now and not angel_feed.is_connected:
        logger.info("Market open — starting live feed")
        angel_feed.start()
    elif not open_now and angel_feed.is_connected:
        logger.info("Market closed — stopping live feed")
        angel_feed.stop()


def _news_job() -> None:
    from .services import sentiment

    try:
        sentiment.ingest_news()
    except Exception as exc:  # noqa: BLE001
        logger.warning("news ingest failed: %s", exc)


def _scrip_refresh_job() -> None:
    from .angel.scrip_master import scrip_master

    try:
        scrip_master.ensure_loaded()
    except Exception as exc:  # noqa: BLE001
        logger.warning("scrip refresh failed: %s", exc)


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler:
        return _scheduler
    sched = BackgroundScheduler(timezone="Asia/Kolkata")
    sched.add_job(
        _snapshot_oi_job, "interval",
        seconds=settings.oi_snapshot_interval, id="oi_snapshot",
        max_instances=1, coalesce=True,
    )
    sched.add_job(
        _feed_manager_job, "interval", seconds=60, id="feed_manager",
        max_instances=1, coalesce=True,
    )
    sched.add_job(_news_job, "interval", minutes=10, id="news", max_instances=1, coalesce=True)
    sched.add_job(_scrip_refresh_job, "cron", hour=8, minute=15, id="scrip_refresh")
    sched.start()
    _scheduler = sched
    logger.info("Scheduler started (OI every %ds, news every 10m)", settings.oi_snapshot_interval)
    return sched


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None
