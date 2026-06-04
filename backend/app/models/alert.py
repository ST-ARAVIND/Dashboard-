"""User-defined price / OI alerts."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class Alert(Base):
    """A threshold alert on a tradable instrument.

    metric:   ltp | percent_change | oi
    operator: above | below
    When the live value crosses the threshold the alert fires once (one-shot):
    it records ``triggered_at`` and goes inactive unless ``repeat`` is set.
    """

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(String(32), index=True)
    symbol: Mapped[str] = mapped_column(String(64))
    exch_seg: Mapped[str] = mapped_column(String(8), default="NSE")

    metric: Mapped[str] = mapped_column(String(16), default="ltp")
    operator: Mapped[str] = mapped_column(String(8), default="above")  # above | below
    threshold: Mapped[float] = mapped_column(Float)
    note: Mapped[str] = mapped_column(String(255), default="")

    active: Mapped[bool] = mapped_column(Boolean, default=True)
    repeat: Mapped[bool] = mapped_column(Boolean, default=False)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    triggered_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "token": self.token,
            "symbol": self.symbol,
            "exch_seg": self.exch_seg,
            "metric": self.metric,
            "operator": self.operator,
            "threshold": self.threshold,
            "note": self.note,
            "active": self.active,
            "repeat": self.repeat,
            "triggered_at": self.triggered_at.isoformat() if self.triggered_at else None,
            "triggered_value": self.triggered_value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
