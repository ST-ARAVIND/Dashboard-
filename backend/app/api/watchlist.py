"""Watchlist CRUD + live snapshot."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Watchlist, WatchlistItem, get_db
from ..services.market_data import market_data

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])

DEFAULT_NAME = "default"


class AddItem(BaseModel):
    token: str
    symbol: str
    exch_seg: str = "NSE"


def _get_or_create(db: Session, name: str = DEFAULT_NAME) -> Watchlist:
    wl = db.scalar(select(Watchlist).where(Watchlist.name == name))
    if not wl:
        wl = Watchlist(name=name)
        db.add(wl)
        db.commit()
        db.refresh(wl)
    return wl


@router.get("")
def get_watchlist(live: bool = True, db: Session = Depends(get_db)) -> dict:
    wl = _get_or_create(db)
    items = [i.as_dict() for i in wl.items]
    if live and items:
        by_exch: dict[str, list[str]] = {}
        for it in items:
            by_exch.setdefault(it["exch_seg"], []).append(it["token"])
        quotes = {q["token"]: q for q in market_data.get_full_quotes(by_exch)}
        for it in items:
            q = quotes.get(it["token"])
            if q:
                it.update(
                    ltp=q.get("ltp"), net_change=q.get("net_change"),
                    percent_change=q.get("percent_change"),
                    volume=q.get("volume"), oi=q.get("oi"),
                )
    return {"name": wl.name, "items": items}


@router.post("")
def add_item(item: AddItem, db: Session = Depends(get_db)) -> dict:
    wl = _get_or_create(db)
    if db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == wl.id, WatchlistItem.token == item.token
        )
    ):
        return {"ok": True, "note": "already present"}
    db.add(WatchlistItem(watchlist_id=wl.id, **item.model_dump()))
    db.commit()
    return {"ok": True}


@router.delete("/{token}")
def remove_item(token: str, db: Session = Depends(get_db)) -> dict:
    wl = _get_or_create(db)
    item = db.scalar(
        select(WatchlistItem).where(
            WatchlistItem.watchlist_id == wl.id, WatchlistItem.token == token
        )
    )
    if not item:
        raise HTTPException(404, "Not in watchlist")
    db.delete(item)
    db.commit()
    return {"ok": True}
