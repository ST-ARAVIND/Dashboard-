"""Angel One scrip master (instrument list) download, cache and lookups.

The OpenAPI scrip master is a large (~100k row) JSON list of every tradable
instrument across NSE/BSE/NFO/MCX/CDS.  We download it once daily, normalize a
few quirky fields, and cache it in SQLite.  Lookup helpers resolve human symbols
("NIFTY", "RELIANCE") to tradable tokens, and build option universes per
underlying/expiry for the chain builder.

Quirks handled:
  * ``strike`` ships multiplied by 100 (paise) -> divided to rupees.
  * ``expiry`` ships as e.g. "26JUN2025" -> kept as-is plus parsed datetime.
  * exchange segment lives in ``exch_seg`` (NSE/BSE/NFO/MCX/CDS).
"""
from __future__ import annotations

import logging
from datetime import datetime

import httpx
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Instrument, SessionLocal

logger = logging.getLogger("angel.scrip_master")

# How long the cache is considered fresh.
_REFRESH_HOURS = 20

# Index underlyings that are European-style (used by the IV/Greeks layer).
EUROPEAN_INDEX_UNDERLYINGS = {
    "NIFTY", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "NIFTYNXT50", "SENSEX", "BANKEX",
}


def _normalize_strike(raw: object) -> float:
    """Angel ships strike * 100; convert to rupees. '-1' means N/A."""
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if val < 0:
        return 0.0
    return round(val / 100.0, 2)


def parse_expiry(expiry: str) -> datetime | None:
    """Parse Angel expiry like '26JUN2025' (15:30 IST close) -> datetime."""
    if not expiry:
        return None
    # strptime matches month abbreviations case-insensitively, so we upper-case
    # the VALUE but must leave the format directives (%d/%b/%Y) untouched.
    val = expiry.upper()
    for fmt in ("%d%b%Y", "%d-%b-%Y", "%d%b%y"):
        try:
            dt = datetime.strptime(val, fmt)
            return dt.replace(hour=15, minute=30)
        except ValueError:
            continue
    return None


class ScripMaster:
    """Downloads, caches and queries the instrument master."""

    def is_stale(self, db: Session) -> bool:
        count = db.scalar(select(func.count()).select_from(Instrument))
        if not count:
            return True
        newest = db.scalar(select(func.max(Instrument.updated_at)))
        if newest is None:
            return True
        age_hours = (datetime.utcnow() - newest).total_seconds() / 3600.0
        return age_hours > _REFRESH_HOURS

    def ensure_loaded(self, force: bool = False) -> int:
        """Download + cache if stale. Returns row count."""
        with SessionLocal() as db:
            if not force and not self.is_stale(db):
                return db.scalar(select(func.count()).select_from(Instrument)) or 0
            return self._download_and_store(db)

    def _download_and_store(self, db: Session) -> int:
        logger.info("Downloading scrip master from %s", settings.scrip_master_url)
        with httpx.Client(timeout=120.0) as http:
            resp = http.get(settings.scrip_master_url)
            resp.raise_for_status()
            rows = resp.json()
        logger.info("Scrip master fetched: %d instruments", len(rows))

        now = datetime.utcnow()
        # Replace the whole table atomically-ish (single transaction).
        db.execute(delete(Instrument))
        batch: list[Instrument] = []
        for r in rows:
            batch.append(
                Instrument(
                    token=str(r.get("token", "")),
                    symbol=str(r.get("symbol", "")),
                    name=str(r.get("name", "")),
                    expiry=str(r.get("expiry", "") or ""),
                    strike=_normalize_strike(r.get("strike")),
                    lotsize=int(float(r.get("lotsize") or 0)),
                    instrumenttype=str(r.get("instrumenttype", "") or ""),
                    exch_seg=str(r.get("exch_seg", "") or ""),
                    tick_size=float(r.get("tick_size") or 0.0),
                    updated_at=now,
                )
            )
            if len(batch) >= 5000:
                db.add_all(batch)
                db.flush()
                batch = []
        if batch:
            db.add_all(batch)
        db.commit()
        count = db.scalar(select(func.count()).select_from(Instrument)) or 0
        logger.info("Scrip master cached: %d rows", count)
        return count

    # ------------------------------------------------------------------ #
    # Lookups
    # ------------------------------------------------------------------ #
    def search(self, query: str, limit: int = 20) -> list[dict]:
        """Fuzzy-ish search by symbol/name, prioritising equities & index F&O."""
        q = (query or "").strip().upper()
        if not q:
            return []
        with SessionLocal() as db:
            like = f"%{q}%"
            stmt = (
                select(Instrument)
                .where(or_(Instrument.symbol.like(like), Instrument.name.like(like)))
                .limit(limit * 5)
            )
            results = db.scalars(stmt).all()

        def rank(inst: Instrument) -> tuple:
            sym = inst.symbol.upper()
            name = inst.name.upper()
            exact = 0 if sym == q or name == q else 1
            starts = 0 if sym.startswith(q) or name.startswith(q) else 1
            # Prefer cash equities and index futures/options over deep OTM legs.
            seg_pref = {"NSE": 0, "BSE": 1, "NFO": 2, "MCX": 3, "CDS": 4}.get(inst.exch_seg, 5)
            return (exact, starts, seg_pref, len(sym))

        results = sorted(results, key=rank)[:limit]
        return [r.as_dict() for r in results]

    def resolve(self, symbol: str, exch_seg: str | None = None) -> dict | None:
        """Resolve an exact trading symbol (optionally within a segment)."""
        sym = (symbol or "").strip().upper()
        with SessionLocal() as db:
            stmt = select(Instrument).where(func.upper(Instrument.symbol) == sym)
            if exch_seg:
                stmt = stmt.where(Instrument.exch_seg == exch_seg)
            inst = db.scalars(stmt.limit(1)).first()
            return inst.as_dict() if inst else None

    def get_by_token(self, token: str) -> dict | None:
        with SessionLocal() as db:
            inst = db.scalars(
                select(Instrument).where(Instrument.token == str(token)).limit(1)
            ).first()
            return inst.as_dict() if inst else None

    def underlying_spot_instrument(self, name: str) -> dict | None:
        """Find the cash/index instrument used as the option's spot.

        In this scrip master NSE cash equities carry instrumenttype '' and a
        '<NAME>-EQ' symbol (e.g. RELIANCE-EQ, token 2885); the spot index also
        carries instrumenttype '' with symbol == name (e.g. NIFTY -> token 26000,
        also present as 'Nifty 50'/AMXIDX). We resolve equities by the -EQ symbol
        first, then fall back to the index spot row.
        """
        name = (name or "").strip().upper()
        with SessionLocal() as db:
            # 1) Cash equity: '<NAME>-EQ' in NSE.
            eq = db.scalars(
                select(Instrument)
                .where(
                    Instrument.exch_seg == "NSE",
                    func.upper(Instrument.symbol) == f"{name}-EQ",
                )
                .limit(1)
            ).first()
            if eq:
                return eq.as_dict()
            # 2) Index spot: symbol exactly equals the name (e.g. NIFTY=26000).
            idx = db.scalars(
                select(Instrument)
                .where(
                    Instrument.exch_seg == "NSE",
                    func.upper(Instrument.symbol) == name,
                    Instrument.strike == 0.0,
                    Instrument.expiry == "",
                )
                .order_by(Instrument.token)  # canonical 26000-style token sorts first
                .limit(1)
            ).first()
            if idx:
                return idx.as_dict()
            # 3) Last resort: any zero-strike NSE row for the name.
            other = db.scalars(
                select(Instrument)
                .where(
                    Instrument.exch_seg == "NSE",
                    Instrument.name == name,
                    Instrument.strike == 0.0,
                    Instrument.expiry == "",
                )
                .limit(1)
            ).first()
            return other.as_dict() if other else None

    def list_expiries(self, underlying: str) -> list[str]:
        """Sorted (soonest-first) list of option expiries for an underlying."""
        name = (underlying or "").strip().upper()
        with SessionLocal() as db:
            rows = db.execute(
                select(Instrument.expiry)
                .where(
                    Instrument.name == name,
                    Instrument.exch_seg == "NFO",
                    Instrument.instrumenttype.in_(("OPTIDX", "OPTSTK")),
                    Instrument.expiry != "",
                )
                .distinct()
            ).all()
        expiries = [r[0] for r in rows]
        expiries.sort(key=lambda e: (parse_expiry(e) or datetime.max))
        return expiries

    def option_universe(self, underlying: str, expiry: str) -> list[dict]:
        """All CE/PE option instruments for an underlying + expiry."""
        name = (underlying or "").strip().upper()
        with SessionLocal() as db:
            rows = db.scalars(
                select(Instrument).where(
                    Instrument.name == name,
                    Instrument.exch_seg == "NFO",
                    Instrument.expiry == expiry,
                    Instrument.instrumenttype.in_(("OPTIDX", "OPTSTK")),
                )
            ).all()
        out = []
        for inst in rows:
            sym = inst.symbol.upper()
            opt_type = "CE" if sym.endswith("CE") else ("PE" if sym.endswith("PE") else "")
            if not opt_type:
                continue
            d = inst.as_dict()
            d["option_type"] = opt_type
            out.append(d)
        return out

    def is_european(self, underlying: str) -> bool:
        return (underlying or "").strip().upper() in EUROPEAN_INDEX_UNDERLYINGS

    def fno_underlyings(self) -> list[str]:
        """Distinct stock names that have stock options (OPTSTK) — the F&O universe."""
        with SessionLocal() as db:
            rows = db.execute(
                select(Instrument.name)
                .where(Instrument.exch_seg == "NFO", Instrument.instrumenttype == "OPTSTK")
                .distinct()
            ).all()
        return sorted({r[0] for r in rows if r[0]})

    def nearest_future(self, underlying: str) -> dict | None:
        """Nearest-expiry futures (FUTIDX/FUTSTK) instrument for an underlying.

        Used as a candle source for indices, whose spot token returns no
        historical data from Angel's getCandleData.
        """
        name = (underlying or "").strip().upper()
        with SessionLocal() as db:
            rows = db.scalars(
                select(Instrument).where(
                    Instrument.name == name,
                    Instrument.exch_seg == "NFO",
                    Instrument.instrumenttype.in_(("FUTIDX", "FUTSTK")),
                    Instrument.expiry != "",
                )
            ).all()
        futs = [r for r in rows]
        if not futs:
            return None
        # Pick the soonest expiry that hasn't passed; else the soonest overall.
        now = datetime.utcnow()
        futs.sort(key=lambda r: (parse_expiry(r.expiry) or datetime.max))
        upcoming = [r for r in futs if (parse_expiry(r.expiry) or datetime.max) >= now]
        chosen = upcoming[0] if upcoming else futs[0]
        return chosen.as_dict()

    def is_index_spot(self, token: str) -> bool:
        """True if the token is an NSE index spot row (no strike/expiry)."""
        inst = self.get_by_token(token)
        if not inst:
            return False
        return (
            inst["exch_seg"] == "NSE"
            and inst["strike"] == 0.0
            and not inst["expiry"]
            and inst["name"].upper() in EUROPEAN_INDEX_UNDERLYINGS
            and not inst["symbol"].upper().endswith("-EQ")
        )


scrip_master = ScripMaster()
