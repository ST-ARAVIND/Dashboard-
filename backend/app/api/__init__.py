"""FastAPI routers."""
from . import (
    auth, instruments, market, chain, oi, sentiment, breadth, watchlist, ws,
    analytics, alerts,
)

routers = [
    auth.router,
    instruments.router,
    market.router,
    chain.router,
    oi.router,
    sentiment.router,
    breadth.router,
    watchlist.router,
    ws.router,
    analytics.router,
    alerts.router,
]

__all__ = ["routers"]
