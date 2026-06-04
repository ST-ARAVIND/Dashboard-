"""Database engine, session factory and declarative base.

The schema is written so that swapping SQLite for Postgres is purely a
``DATABASE_URL`` change — no model edits required.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from ..config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ``check_same_thread`` only matters for SQLite; harmless to compute generally.
_connect_args = (
    {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
)

engine = create_engine(
    settings.database_url,
    connect_args=_connect_args,
    pool_pre_ping=True,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def init_db() -> None:
    """Create all tables. Safe to call repeatedly."""
    # Import side-effect: ensure every model is registered on Base.metadata.
    from . import instrument, candle, news, watchlist, oi_snapshot, alert  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
