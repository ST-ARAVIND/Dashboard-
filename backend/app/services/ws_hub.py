"""Frontend websocket relay hub.

Bridges the Angel feed (which delivers ticks on a background thread) to any
number of connected browser websocket clients, fanning out normalized ticks.
Angel tokens are NEVER sent to the browser — only normalized tick payloads.

The hub keeps a reference count per token so it can subscribe upstream on first
interest and unsubscribe when the last client drops it.
"""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict

from fastapi import WebSocket

from ..angel.feed import MODE_SNAP_QUOTE, angel_feed
from ..angel.scrip_master import scrip_master

logger = logging.getLogger("services.ws_hub")


class WSHub:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()
        self._loop: asyncio.AbstractEventLoop | None = None
        # token -> set of client websockets interested in it
        self._interest: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()
        # Last tick per token so a new client gets an immediate snapshot.
        self._last_tick: dict[str, dict] = {}

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the main event loop and wire the feed sink (thread-safe)."""
        self._loop = loop
        angel_feed.set_sink(self._on_upstream_tick)

    # ------------------------------------------------------------------ #
    # Called from the Angel feed thread.
    # ------------------------------------------------------------------ #
    def _on_upstream_tick(self, tick: dict) -> None:
        token = tick.get("token")
        if token:
            self._last_tick[token] = tick
        if self._loop is None:
            return
        # Hop from the feed thread onto the event loop safely.
        self._loop.call_soon_threadsafe(asyncio.create_task, self._broadcast(tick))

        # Evaluate price/OI alerts against this tick; broadcast any that fire.
        try:
            from .alerts import alert_manager

            fired = alert_manager.evaluate(tick)
            for f in fired:
                msg = {
                    "type": "alert",
                    "id": f["id"],
                    "symbol": f["symbol"],
                    "token": f["token"],
                    "metric": f["metric"],
                    "operator": f["operator"],
                    "threshold": f["threshold"],
                    "value": f["value"],
                    "note": f.get("note", ""),
                    "ts": tick.get("ts"),
                }
                self._loop.call_soon_threadsafe(asyncio.create_task, self._broadcast_all(msg))
        except Exception as exc:  # noqa: BLE001
            logger.debug("alert eval error: %s", exc)

    async def _broadcast_all(self, msg: dict) -> None:
        """Send a message (e.g. a fired alert) to every connected client."""
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(msg)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    async def _broadcast(self, tick: dict) -> None:
        token = tick.get("token")
        targets = list(self._interest.get(token, ())) if token else list(self._clients)
        dead = []
        for ws in targets:
            try:
                await ws.send_json(tick)
            except Exception:  # noqa: BLE001
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    # ------------------------------------------------------------------ #
    # Client lifecycle
    # ------------------------------------------------------------------ #
    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self._clients.add(ws)
        logger.info("WS client connected (%d total)", len(self._clients))

    async def disconnect(self, ws: WebSocket) -> None:
        self._clients.discard(ws)
        # Drop this client's interests; unsubscribe upstream where it was the last.
        drop_tokens = []
        for token, subs in list(self._interest.items()):
            if ws in subs:
                subs.discard(ws)
                if not subs:
                    drop_tokens.append(token)
                    del self._interest[token]
        if drop_tokens:
            angel_feed.unsubscribe(drop_tokens)
        logger.info("WS client disconnected (%d total)", len(self._clients))

    async def handle_subscribe(self, ws: WebSocket, instruments: list[dict]) -> None:
        """instruments: [{"token","exch_seg"}]. Subscribe client + upstream."""
        new_upstream: list[dict] = []
        for inst in instruments:
            token = str(inst.get("token"))
            if not token:
                continue
            exch_seg = inst.get("exch_seg") or self._lookup_seg(token)
            first_interest = token not in self._interest or not self._interest[token]
            self._interest[token].add(ws)
            if first_interest:
                new_upstream.append({"token": token, "exch_seg": exch_seg})
            # Immediately replay last known tick to this client.
            if token in self._last_tick:
                try:
                    await ws.send_json(self._last_tick[token])
                except Exception:  # noqa: BLE001
                    pass
        if new_upstream:
            angel_feed.subscribe(new_upstream, mode=MODE_SNAP_QUOTE)

    async def handle_unsubscribe(self, ws: WebSocket, tokens: list[str]) -> None:
        drop = []
        for token in tokens:
            token = str(token)
            subs = self._interest.get(token)
            if subs and ws in subs:
                subs.discard(ws)
                if not subs:
                    drop.append(token)
                    self._interest.pop(token, None)
        if drop:
            angel_feed.unsubscribe(drop)

    @staticmethod
    def _lookup_seg(token: str) -> str:
        inst = scrip_master.get_by_token(token)
        return inst["exch_seg"] if inst else "NSE"


ws_hub = WSHub()
