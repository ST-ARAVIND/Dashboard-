"""News ingestion + sentiment scoring (provider-agnostic).

Providers (config NEWS_PROVIDER):
  * rss     -> free RSS feeds from Indian financial outlets (no key).
  * newsapi -> https://newsapi.org/ (requires NEWS_API_KEY).

Sentiment (config SENTIMENT_MODEL):
  * vader   -> fast, no model download (default).
  * finbert -> finance-tuned transformer (lazy-loaded; needs transformers+torch).

Headlines are mapped to underlyings via keyword/entity match against the
instrument master, scored, de-duplicated and stored in SQLite.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import datetime, timezone
from time import mktime

import feedparser
import httpx
from sqlalchemy import desc, func, select

from ..config import settings
from ..models import NewsArticle, SessionLocal
from ..models.instrument import Instrument

logger = logging.getLogger("services.sentiment")

# Indian financial RSS feeds (provider=rss).
# Curated for freshness — verified live: ET and Livemint update through the day,
# Hindu BusinessLine is the freshest. (Moneycontrol & Business Standard RSS were
# dropped: their public feeds were stale by months / returning empty.)
RSS_FEEDS = [
    ("Economic Times Markets", "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"),
    ("Economic Times Stocks", "https://economictimes.indiatimes.com/markets/stocks/news/rssfeeds/2146843.cms"),
    ("Livemint Markets", "https://www.livemint.com/rss/markets"),
    ("Livemint Money", "https://www.livemint.com/rss/money"),
    ("Hindu BusinessLine", "https://www.thehindubusinessline.com/markets/feeder/default.rss"),
]

# Common-word symbols to skip when matching tickers (avoid false positives).
_STOPWORD_TICKERS = {"PVR", "IT", "MOIL", "ACC", "BSE", "NSE", "GAIL", "INFO", "ALL", "ANY", "ON", "OR"}


# ---------------------------------------------------------------------- #
# Sentiment scorers
# ---------------------------------------------------------------------- #
class _VaderScorer:
    def __init__(self) -> None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        self._a = SentimentIntensityAnalyzer()
        self.name = "vader"

    def score(self, text: str) -> tuple[float, str]:
        comp = self._a.polarity_scores(text or "")["compound"]
        return comp, _label(comp)


class _FinBertScorer:
    def __init__(self) -> None:
        from transformers import pipeline  # lazy heavy import

        self._pipe = pipeline("sentiment-analysis", model="ProsusAI/finbert")
        self.name = "finbert"

    def score(self, text: str) -> tuple[float, str]:
        if not text:
            return 0.0, "neutral"
        res = self._pipe(text[:512])[0]
        label = res["label"].lower()
        signed = {"positive": 1, "negative": -1, "neutral": 0}.get(label, 0)
        return round(signed * res["score"], 4), label


def _label(score: float) -> str:
    if score >= 0.05:
        return "positive"
    if score <= -0.05:
        return "negative"
    return "neutral"


_scorer = None


def get_scorer():
    """Lazily build the configured scorer; fall back to VADER on failure."""
    global _scorer
    if _scorer is not None:
        return _scorer
    model = settings.sentiment_model.lower()
    if model == "finbert":
        try:
            _scorer = _FinBertScorer()
            logger.info("Using FinBERT sentiment model")
            return _scorer
        except Exception as exc:  # noqa: BLE001
            logger.warning("FinBERT unavailable (%s); falling back to VADER", exc)
    _scorer = _VaderScorer()
    return _scorer


# ---------------------------------------------------------------------- #
# Providers
# ---------------------------------------------------------------------- #
def _fetch_rss() -> list[dict]:
    articles = []
    for source, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
        except Exception as exc:  # noqa: BLE001
            logger.warning("RSS fetch failed for %s: %s", source, exc)
            continue
        for e in feed.entries[:40]:
            published = datetime.now(timezone.utc)
            if getattr(e, "published_parsed", None):
                try:
                    published = datetime.fromtimestamp(mktime(e.published_parsed), tz=timezone.utc)
                except Exception:  # noqa: BLE001
                    pass
            articles.append(
                {
                    "source": source,
                    "title": getattr(e, "title", ""),
                    "summary": re.sub("<[^<]+?>", "", getattr(e, "summary", ""))[:500],
                    "url": getattr(e, "link", ""),
                    "published_at": published,
                }
            )
    return articles


def _fetch_newsapi() -> list[dict]:
    if not settings.news_api_key:
        logger.warning("NEWS_PROVIDER=newsapi but NEWS_API_KEY is empty")
        return []
    params = {
        "q": "(NSE OR BSE OR Sensex OR Nifty OR India stock market)",
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": 50,
        "apiKey": settings.news_api_key,
    }
    try:
        with httpx.Client(timeout=30) as http:
            resp = http.get("https://newsapi.org/v2/everything", params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.error("NewsAPI fetch failed: %s", exc)
        return []
    out = []
    for a in data.get("articles", []):
        published = datetime.now(timezone.utc)
        if a.get("publishedAt"):
            try:
                published = datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00"))
            except Exception:  # noqa: BLE001
                pass
        out.append(
            {
                "source": (a.get("source") or {}).get("name", "NewsAPI"),
                "title": a.get("title", ""),
                "summary": (a.get("description") or "")[:500],
                "url": a.get("url", ""),
                "published_at": published,
            }
        )
    return out


def fetch_raw_articles() -> list[dict]:
    if settings.news_provider.lower() == "newsapi":
        arts = _fetch_newsapi()
        if arts:
            return arts
        logger.info("NewsAPI returned nothing; falling back to RSS")
    return _fetch_rss()


# ---------------------------------------------------------------------- #
# Ticker mapping
# ---------------------------------------------------------------------- #
_ticker_cache: dict[str, str] | None = None


def _build_ticker_index() -> dict[str, str]:
    """Map upper-cased underlying NAME -> canonical name, for top equities+indices."""
    global _ticker_cache
    if _ticker_cache is not None:
        return _ticker_cache
    index: dict[str, str] = {}
    with SessionLocal() as db:
        # NSE cash equities carry a '<NAME>-EQ' symbol (instrumenttype is '').
        rows = db.scalars(
            select(Instrument.name)
            .where(Instrument.exch_seg == "NSE", Instrument.symbol.like("%-EQ"))
            .distinct()
        ).all()
    for name in rows:
        n = (name or "").strip().upper()
        if len(n) >= 3 and n not in _STOPWORD_TICKERS:
            index[n] = n
    # Always include the big indices.
    for idx in ("NIFTY", "BANKNIFTY", "SENSEX", "FINNIFTY", "MIDCPNIFTY"):
        index[idx] = idx
    _ticker_cache = index
    return index


def map_tickers(text: str) -> list[str]:
    idx = _build_ticker_index()
    upper = (text or "").upper()
    words = set(re.findall(r"[A-Z&]{3,}", upper))
    matched = sorted(w for w in words if w in idx)
    return matched[:8]


# ---------------------------------------------------------------------- #
# Ingest
# ---------------------------------------------------------------------- #
def _uid(article: dict) -> str:
    key = (article.get("url") or article.get("title") or "").strip().lower()
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:32]


def ingest_news() -> int:
    """Fetch, score, map and store new articles. Returns count of NEW rows."""
    raw = fetch_raw_articles()
    if not raw:
        return 0
    scorer = get_scorer()
    new_count = 0
    seen_uids: set[str] = set()  # de-dup within this run (feeds overlap)
    with SessionLocal() as db:
        for a in raw:
            uid = _uid(a)
            if uid in seen_uids:
                continue
            seen_uids.add(uid)
            exists = db.scalar(select(NewsArticle.id).where(NewsArticle.uid == uid))
            if exists:
                continue
            text = f"{a['title']}. {a.get('summary', '')}"
            score, label = scorer.score(text)
            tickers = map_tickers(text)
            db.add(
                NewsArticle(
                    uid=uid,
                    source=a["source"],
                    title=a["title"],
                    summary=a.get("summary", ""),
                    url=a.get("url", ""),
                    published_at=a["published_at"].replace(tzinfo=None),
                    sentiment_score=score,
                    sentiment_label=label,
                    sentiment_model=scorer.name,
                    tickers=",".join(tickers),
                )
            )
            new_count += 1
        db.commit()
    logger.info("Ingested %d new articles", new_count)
    return new_count


# ---------------------------------------------------------------------- #
# Queries
# ---------------------------------------------------------------------- #
def market_feed(limit: int = 50) -> dict:
    with SessionLocal() as db:
        rows = db.scalars(
            select(NewsArticle).order_by(desc(NewsArticle.published_at)).limit(limit)
        ).all()
        avg = db.scalar(select(func.avg(NewsArticle.sentiment_score)))
    articles = [r.as_dict() for r in rows]
    return {
        "count": len(articles),
        "avg_sentiment": round(avg, 4) if avg is not None else None,
        "avg_label": _label(avg) if avg is not None else "neutral",
        "articles": articles,
    }


def symbol_feed(symbol: str, limit: int = 30) -> dict:
    sym = symbol.strip().upper()
    with SessionLocal() as db:
        rows = db.scalars(
            select(NewsArticle)
            .where(NewsArticle.tickers.like(f"%{sym}%"))
            .order_by(desc(NewsArticle.published_at))
            .limit(limit)
        ).all()
    # Filter precisely (LIKE can over-match substrings).
    filtered = [r for r in rows if sym in r.tickers.split(",")]
    scores = [r.sentiment_score for r in filtered]
    return {
        "symbol": sym,
        "count": len(filtered),
        "avg_sentiment": round(sum(scores) / len(scores), 4) if scores else None,
        "articles": [r.as_dict() for r in filtered],
    }
