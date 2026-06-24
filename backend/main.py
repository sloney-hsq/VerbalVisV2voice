"""
VerbalVis FastAPI entry point.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from db import initialize_db
from realtime import RealtimeSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger(__name__)

app = FastAPI(title="VerbalVis API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    log.info("Initialising DuckDB…")
    initialize_db()
    log.info("Ready.")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    log.info("Client connected: %s", session_id)

    session = RealtimeSession(client_ws=websocket, session_id=session_id)
    try:
        await session.start()
    except WebSocketDisconnect:
        log.info("Client disconnected: %s", session_id)
    except Exception as exc:
        log.exception("Session error: %s", exc)
