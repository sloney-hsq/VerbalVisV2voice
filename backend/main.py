"""VerbalVis FastAPI entry point.

The current dashboard state is intentionally single-session. A second browser is
rejected instead of sharing filters and views with the active participant.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
import uuid

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db import initialize_db
from realtime import QWEN_MODEL, QWEN_TURN_DETECTION, QwenRealtimeSession

FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"

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

_active_session_lock = asyncio.Lock()
_active_session_id: str | None = None


@app.on_event("startup")
async def startup_event() -> None:
    log.info("Initialising DuckDB...")
    initialize_db()
    log.info("Ready.")


@app.get("/health")
async def health_check() -> dict[str, str | bool | None]:
    return {
        "status": "ok",
        "single_session": True,
        "active_session_id": _active_session_id,
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    global _active_session_id

    await websocket.accept()
    session_id = f"session-{uuid.uuid4().hex[:8]}"

    async with _active_session_lock:
        if _active_session_id is not None:
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Another VerbalVis study session is already active.",
                }
            )
            await websocket.close(code=1013)
            return
        _active_session_id = session_id

    analysis_id = _analysis_id_from_query(websocket)
    log.info(
        "Client connected: %s analysis=%s model=%s turn_detection=%s",
        session_id,
        analysis_id or "-",
        QWEN_MODEL,
        QWEN_TURN_DETECTION,
    )

    session = QwenRealtimeSession(
        client_ws=websocket,
        session_id=session_id,
        model=QWEN_MODEL,
        analysis_id=analysis_id,
    )
    try:
        await session.start()
    except WebSocketDisconnect:
        log.info("Client disconnected: %s", session_id)
    except Exception as exc:
        log.exception("Qwen session error: %s", exc)
    finally:
        async with _active_session_lock:
            if _active_session_id == session_id:
                _active_session_id = None


def _analysis_id_from_query(websocket: WebSocket) -> str | None:
    value = (
        websocket.query_params.get("analysis_id")
        or websocket.query_params.get("analysisId")
        or ""
    ).strip()
    return value or None


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{path:path}")
    async def serve_frontend(path: str) -> FileResponse:
        requested = FRONTEND_DIST / path
        if requested.is_file():
            return FileResponse(requested)
        return FileResponse(FRONTEND_DIST / "index.html")
