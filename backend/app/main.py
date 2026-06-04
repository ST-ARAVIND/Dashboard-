"""FastAPI application entrypoint.

Wires together config, DB, the Angel session/feed, the scheduler and all API
routers.  On startup it: creates tables, loads the scrip master, attempts an
Angel login (if credentials are present), binds the websocket hub to the running
event loop, starts the live feed and the scheduler.
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .angel.session import AngelAuthError
from .api import routers
from .config import settings
from .models import init_db
from .utils.market_hours import market_state

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s — %(message)s",
)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ANN201
    # --- DB ---
    init_db()
    logger.info("Database initialized at %s", settings.database_url)

    # --- Scrip master (best-effort; doesn't need Angel auth) ---
    from .angel.scrip_master import scrip_master

    try:
        count = await asyncio.to_thread(scrip_master.ensure_loaded)
        logger.info("Scrip master ready: %d instruments", count)
    except Exception as exc:  # noqa: BLE001
        logger.error("Scrip master load failed: %s", exc)

    # --- Bind websocket hub to this event loop ---
    from .services.ws_hub import ws_hub

    ws_hub.bind_loop(asyncio.get_running_loop())

    # --- Angel auth + live feed (only if credentials present) ---
    if settings.angel_credentials_present:
        from .angel.feed import angel_feed
        from .angel.session import angel_session

        from .utils.market_hours import is_market_open

        try:
            await asyncio.to_thread(angel_session.login)
            logger.info("Angel One session established")
            # Only open the live feed during market hours — outside hours Angel's
            # socket churns reconnects with no data. The scheduler's feed-manager
            # job starts it automatically when the market opens.
            if is_market_open():
                angel_feed.start()
            else:
                logger.info("Market closed — live feed will start at market open.")
        except Exception as exc:  # noqa: BLE001
            logger.error("Angel One login failed (continuing without live data): %s", exc)
    else:
        logger.warning(
            "Angel One credentials missing — running in degraded mode "
            "(search/news work; quotes/chain/feed need credentials)."
        )

    # --- Scheduler ---
    from .scheduler import start_scheduler, stop_scheduler

    start_scheduler()

    yield

    # --- Shutdown ---
    stop_scheduler()
    try:
        from .angel.feed import angel_feed

        angel_feed.stop()
    except Exception:  # noqa: BLE001
        pass


app = FastAPI(
    title="Indian Market Intelligence Dashboard",
    version="1.0.0",
    description="Real-time Indian equities & F&O analytics on Angel One SmartAPI.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(AngelAuthError)
async def angel_auth_handler(request: Request, exc: AngelAuthError):  # noqa: ANN201
    """Surface missing/expired Angel auth as a clean 503 instead of a 500."""
    return JSONResponse(
        status_code=503,
        content={
            "detail": str(exc),
            "hint": "Set Angel One credentials in .env and POST /api/auth/login.",
        },
    )


for r in routers:
    app.include_router(r)


@app.get("/api/health")
def health() -> dict:
    from .angel.feed import angel_feed
    from .angel.session import angel_session

    return {
        "status": "ok",
        "market": market_state(),
        "angel": angel_session.status(),
        "feed": angel_feed.status(),
    }


@app.get("/")
def root() -> dict:
    return {"name": "Indian Market Intelligence Dashboard API", "docs": "/docs"}
