"""User watchlists."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import ForeignKey, Integer, String, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watchlist_id: Mapped[int] = mapped_column(ForeignKey("watchlists.id", ondelete="CASCADE"))
    token: Mapped[str] = mapped_column(String(32))
    symbol: Mapped[str] = mapped_column(String(64))
    exch_seg: Mapped[str] = mapped_column(String(8), default="NSE")

    watchlist: Mapped["Watchlist"] = relationship(back_populates="items")

    __table_args__ = (UniqueConstraint("watchlist_id", "token", name="uq_watchlist_token"),)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "token": self.token,
            "symbol": self.symbol,
            "exch_seg": self.exch_seg,
        }
