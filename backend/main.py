"""
VerbalVis FastAPI entry point.
"""

from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from db import initialize_db
from realtime_qwen import QwenRealtimeSession

QWEN_REALTIME_MODEL = "qwen3.5-omni-plus-realtime"

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
    log.info("Initialising DuckDB...")
    initialize_db()
    log.info("Ready.")


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Default VerbalVis realtime endpoint: Qwen only."""
    await _run_qwen_session(websocket)


@app.websocket("/ws/qwen")
async def websocket_qwen_endpoint(websocket: WebSocket) -> None:
    """Compatibility alias for the Qwen-only realtime endpoint."""
    await _run_qwen_session(websocket)


async def _run_qwen_session(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    log.info("Client connected (qwen): %s model=%s", session_id, QWEN_REALTIME_MODEL)

    session = QwenRealtimeSession(
        client_ws=websocket,
        session_id=session_id,
        model=QWEN_REALTIME_MODEL,
    )
    try:
        await session.start()
    except WebSocketDisconnect:
        log.info("Client disconnected: %s", session_id)
    except Exception as exc:
        log.exception("Qwen session error: %s", exc)
