"""
VerbalVis FastAPI entry point.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from db import initialize_db
import tool_runtime_patch  # noqa: F401 - installs managed-view refresh ownership
from realtime_nonpreemptive import QWEN_TURN_DETECTION, QwenRealtimeSession

QWEN_REALTIME_MODEL = "qwen3.5-omni-plus-realtime"
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


async def _run_qwen_session(websocket: WebSocket) -> None:
    await websocket.accept()
    session_id = f"session-{uuid.uuid4().hex[:8]}"
    analysis_id = _analysis_id_from_query(websocket)
    log.info(
        "Client connected (qwen): %s analysis=%s model=%s turn_detection=%s",
        session_id,
        analysis_id or "-",
        QWEN_REALTIME_MODEL,
        QWEN_TURN_DETECTION,
    )

    session = QwenRealtimeSession(
        client_ws=websocket,
        session_id=session_id,
        model=QWEN_REALTIME_MODEL,
        analysis_id=analysis_id,
    )
    try:
        await session.start()
    except WebSocketDisconnect:
        log.info("Client disconnected: %s", session_id)
    except Exception as exc:
        log.exception("Qwen session error: %s", exc)


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
