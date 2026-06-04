"""FastAPI routers."""
from . import auth, instruments, market, chain, oi, sentiment, breadth, watchlist, ws

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
]

__all__ = ["routers"]
