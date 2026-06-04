"""Intraday open-interest snapshots for delta-OI and OI-trend charts."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class OISnapshot(Base):
    """A point-in-time OI / LTP / volume reading for one option token.

    Written on a schedule (default every 3 min during market hours) so the
    analytics layer can compute change-in-OI and render OI-trend charts.
    """

    __tablename__ = "oi_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(32), index=True)
    underlying: Mapped[str] = mapped_column(String(64), index=True)  # e.g. NIFTY
    expiry: Mapped[str] = mapped_column(String(16), default="", index=True)
    strike: Mapped[float] = mapped_column(Float, default=0.0)
    option_type: Mapped[str] = mapped_column(String(4), default="")  # CE / PE
    ltp: Mapped[float] = mapped_column(Float, default=0.0)
    oi: Mapped[float] = mapped_column(Float, default=0.0)
    volume: Mapped[float] = mapped_column(Float, default=0.0)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        Index("ix_oi_underlying_expiry_ts", "underlying", "expiry", "timestamp"),
    )
