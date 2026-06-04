"""Frontend live-tick websocket relay.

Protocol (client -> server JSON messages):
    {"action": "subscribe",   "instruments": [{"token": "...", "exch_seg": "NFO"}]}
    {"action": "unsubscribe", "tokens": ["..."]}
    {"action": "ping"}

Server -> client:
    normalized tick objects  {"type": "tick", "token": "...", "ltp": ..., "oi": ...}
    {"type": "pong"}
    {"type": "market_state", ...}
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services.ws_hub import ws_hub
from ..utils.market_hours import market_state

logger = logging.getLogger("api.ws")

router = APIRouter(tags=["ws"])


@router.websocket("/ws")
async def ws_endpoint(websocket: WebSocket) -> None:
    await ws_hub.connect(websocket)
    # Greet with current market state so the UI can render closed/open immediately.
    await websocket.send_json({"type": "market_state", **market_state()})
    try:
        while True:
            msg = await websocket.receive_json()
            action = msg.get("action")
            if action == "subscribe":
                await ws_hub.handle_subscribe(websocket, msg.get("instruments", []))
            elif action == "unsubscribe":
                await ws_hub.handle_unsubscribe(websocket, msg.get("tokens", []))
            elif action == "ping":
                await websocket.send_json({"type": "pong"})
            elif action == "market_state":
                await websocket.send_json({"type": "market_state", **market_state()})
    except WebSocketDisconnect:
        await ws_hub.disconnect(websocket)
    except Exception as exc:  # noqa: BLE001
        logger.debug("ws error: %s", exc)
        await ws_hub.disconnect(websocket)
