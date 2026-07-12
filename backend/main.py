"""VerbalVis FastAPI entry point.

One browser page owns one backend WebSocket and one Qwen Realtime session. The
microphone may be started and stopped repeatedly without creating another model
session. Dashboard state is intentionally single-participant and in-memory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# Load backend/.env (or a parent .env) before realtime.py reads configuration.
load_dotenv()
if not os.getenv("QWEN_WORKSPACE_ID"):
    workspace_alias = (
        os.getenv("DASHSCOPE_WORKSPACE_ID")
        or os.getenv("WORKSPACE_ID")
        or ""
    ).strip()
    if workspace_alias:
        os.environ["QWEN_WORKSPACE_ID"] = workspace_alias

from db import initialize_db  # noqa: E402
from realtime import (  # noqa: E402
    QWEN_API_KEY,
    QWEN_AUDIO_FORMAT,
    QWEN_INPUT_SAMPLE_RATE,
    QWEN_MODEL,
    QWEN_OUTPUT_SAMPLE_RATE,
    QWEN_REALTIME_URL,
    QWEN_TURN_DETECTION,
    QWEN_VOICE,
    QWEN_WORKSPACE_ID,
    QwenRealtimeSession,
)
from tools import get_views_for_frontend, init_views  # noqa: E402

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


def qwen_configuration_error() -> str | None:
    """Return an actionable configuration message, or None when ready."""
    if not QWEN_API_KEY:
        return (
            "Qwen Realtime is not configured: set DASHSCOPE_API_KEY in "
            "backend/.env and restart the backend."
        )
    return None


@app.on_event("startup")
async def startup_event() -> None:
    log.info("Initialising DuckDB...")
    initialize_db()
    config_error = qwen_configuration_error()
    if config_error:
        log.error(config_error)
    else:
        endpoint_mode = (
            "QWEN_REALTIME_URL"
            if QWEN_REALTIME_URL
            else "QWEN_WORKSPACE_ID"
            if QWEN_WORKSPACE_ID
            else "DashScope public endpoint"
        )
        log.info("Qwen Realtime configuration ready via %s.", endpoint_mode)
    log.info("Ready.")


@app.get("/health")
async def health_check() -> dict[str, str | bool | None]:
    config_error = qwen_configuration_error()
    return {
        "status": "ok",
        "single_session": True,
        "active_session_id": _active_session_id,
        "qwen_configured": qwen_configuration_error() is None,
        "qwen_configuration_error": config_error,
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

    try:
        config_error = qwen_configuration_error()
        if config_error:
            await _serve_configuration_error(
                websocket,
                session_id=session_id,
                analysis_id=analysis_id,
                message=config_error,
            )
            return

        session = QwenRealtimeSession(
            client_ws=websocket,
            session_id=session_id,
            model=QWEN_MODEL,
            analysis_id=analysis_id,
        )
        await session.start()
    except WebSocketDisconnect:
        log.info("Client disconnected: %s", session_id)
    except Exception as exc:
        log.exception("Qwen session error: %s", exc)
    finally:
        async with _active_session_lock:
            if _active_session_id == session_id:
                _active_session_id = None


async def _serve_configuration_error(
    websocket: WebSocket,
    *,
    session_id: str,
    analysis_id: str | None,
    message: str,
) -> None:
    """Keep the dashboard visible and report one non-retrying config error."""
    init_views()
    await websocket.send_json(
        {
            "type": "init",
            "views": get_views_for_frontend(),
            "session_id": session_id,
            "analysis_id": analysis_id or session_id,
            "mode": "barge_in",
            "condition_code": "fd_voice",
            "input_mode": "semantic_vad",
            "turn_detection": QWEN_TURN_DETECTION,
            "provider": "qwen",
            "model": QWEN_MODEL,
            "voice": QWEN_VOICE,
            "input_audio_rate": QWEN_INPUT_SAMPLE_RATE,
            "output_audio_rate": QWEN_OUTPUT_SAMPLE_RATE,
            "audio_format": QWEN_AUDIO_FORMAT,
        }
    )
    await websocket.send_json(
        {
            "type": "configuration_error",
            "message": message,
            "required": ["DASHSCOPE_API_KEY"],
            "optional": ["QWEN_WORKSPACE_ID", "QWEN_REALTIME_URL"],
        }
    )
    await websocket.send_json(
        {
            "type": "runtime_state",
            "phase": "configuration_error",
            "tool_running": False,
            "tools": [],
        }
    )
    log.error("Session %s cannot start Qwen: %s", session_id, message)

    while True:
        try:
            raw = await websocket.receive_text()
        except WebSocketDisconnect:
            return
        except RuntimeError:
            return
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if payload.get("type") in {"close", "disconnect"}:
            return


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
