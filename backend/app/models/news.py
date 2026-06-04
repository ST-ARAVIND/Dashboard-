"""News articles with sentiment scores."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import Float, Integer, String, Text, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class NewsArticle(Base):
    """A news headline + sentiment score, optionally mapped to tickers."""

    __tablename__ = "news_articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Stable hash of the URL/title used to de-duplicate across refreshes.
    uid: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(64), default="")
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime, index=True, default=datetime.utcnow)

    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)  # -1..1
    sentiment_label: Mapped[str] = mapped_column(String(16), default="neutral")
    sentiment_model: Mapped[str] = mapped_column(String(16), default="vader")

    # Comma-separated underlying names matched to this article (e.g. "NIFTY,RELIANCE").
    tickers: Mapped[str] = mapped_column(String(255), default="", index=True)

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "source": self.source,
            "title": self.title,
            "summary": self.summary,
            "url": self.url,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "sentiment_score": round(self.sentiment_score, 4),
            "sentiment_label": self.sentiment_label,
            "sentiment_model": self.sentiment_model,
            "tickers": [t for t in self.tickers.split(",") if t],
        }
