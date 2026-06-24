"""
VerbalVis FastAPI entry point.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from db import initialize_db
from realtime import RealtimeSession, _LOG_ROOT

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
    _active_sessions[session_id] = session
    try:
        await session.start()
    except WebSocketDisconnect:
        log.info("Client disconnected: %s", session_id)
    except Exception as exc:
        log.exception("Session error: %s", exc)
    finally:
        _active_sessions.pop(session_id, None)


# Track active sessions so upload endpoint can find the log dir
_active_sessions: dict[str, RealtimeSession] = {}


@app.post("/upload-recording")
async def upload_recording(
    file: UploadFile = File(...),
    session_id: str = Form(""),
) -> dict[str, str]:
    """Receive screen recording from frontend and save to session log dir."""
    # Find the session's log dir
    session = _active_sessions.get(session_id)
    if session and session._log_dir:
        save_dir = session._log_dir
    else:
        # Fallback: find the most recent log dir
        log_dirs = sorted(_LOG_ROOT.glob("*"), key=lambda p: p.name, reverse=True)
        save_dir = log_dirs[0] if log_dirs else _LOG_ROOT
        save_dir.mkdir(parents=True, exist_ok=True)

    dest = save_dir / "screen_recording.webm"
    with open(dest, "wb") as f:
        content = await file.read()
        f.write(content)

    log.info("Saved screen recording: %s (%.1f MB)", dest, len(content) / 1024 / 1024)
    return {"status": "ok", "path": str(dest)}
