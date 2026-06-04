"""Historical candle cache."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Candle(Base):
    """A single OHLCV candle for (token, interval, timestamp)."""

    __tablename__ = "candles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(32), index=True)
    exchange: Mapped[str] = mapped_column(String(8), default="NSE")
    interval: Mapped[str] = mapped_column(String(16), index=True)  # ONE_MINUTE, ONE_DAY, ...
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    open: Mapped[float] = mapped_column(Float)
    high: Mapped[float] = mapped_column(Float)
    low: Mapped[float] = mapped_column(Float)
    close: Mapped[float] = mapped_column(Float)
    volume: Mapped[float] = mapped_column(Float, default=0.0)

    __table_args__ = (
        UniqueConstraint("token", "interval", "timestamp", name="uq_candle"),
    )
