"""Instrument master cache (Angel One scrip master)."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Index, Integer, String, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Instrument(Base):
    """A single tradable instrument from the Angel One scrip master.

    Fields mirror the OpenAPIScripMaster.json record:
        token, symbol, name, expiry, strike, lotsize, instrumenttype, exch_seg, tick_size
    """

    __tablename__ = "instruments"

    # Angel's instrument token is the natural key (unique per exchange segment row).
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(64), index=True)  # trading symbol e.g. NIFTY25JUN24500CE
    name: Mapped[str] = mapped_column(String(64), index=True, default="")  # underlying name e.g. NIFTY
    expiry: Mapped[str] = mapped_column(String(16), default="", index=True)  # e.g. 26JUN2025
    strike: Mapped[float] = mapped_column(Float, default=0.0)  # in paise as Angel ships it; normalized on load
    lotsize: Mapped[int] = mapped_column(Integer, default=0)
    instrumenttype: Mapped[str] = mapped_column(String(16), default="", index=True)  # EQ/FUTIDX/OPTIDX/...
    exch_seg: Mapped[str] = mapped_column(String(8), default="", index=True)  # NSE/BSE/NFO/MCX/CDS
    tick_size: Mapped[float] = mapped_column(Float, default=0.0)

    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        Index("ix_instrument_name_seg_type", "name", "exch_seg", "instrumenttype"),
        Index("ix_instrument_name_expiry", "name", "expiry"),
    )

    def as_dict(self) -> dict:
        return {
            "token": self.token,
            "symbol": self.symbol,
            "name": self.name,
            "expiry": self.expiry,
            "strike": self.strike,
            "lotsize": self.lotsize,
            "instrumenttype": self.instrumenttype,
            "exch_seg": self.exch_seg,
            "tick_size": self.tick_size,
        }
