"""
VerbalVis Realtime API manager — Qwen-Omni-Realtime variant.

Bridges the frontend WebSocket and Alibaba DashScope's Qwen-Omni-Realtime
WebSocket. The frontend protocol stays identical to the OpenAI relay
(realtime.py); only the upstream provider differs.

Uses qwen3.5-omni-plus-realtime as the fixed upstream model. Qwen semantic
VAD is the only interruption detector; speech_started immediately cancels the
active response and clears frontend playback.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import datetime
import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import websockets
from dotenv import load_dotenv
from fastapi import WebSocket, WebSocketDisconnect

from logging_utils import resolve_session_log_dir, safe_log_token
from prompts import build_system_prompt
from tools import (
    TOOL_SCHEMAS,
    activate_state_scope,
    execute_tool,
    get_active_filters_for_frontend,
    get_views_for_frontend,
    log_tool_call,
    normalize_tool_arguments,
    persist_active_state_scope,
    realtime_state,
)

load_dotenv()
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Per-session logging (mirrors realtime.py so log layout stays consistent).
# ---------------------------------------------------------------------------
_LOG_ROOT = Path(__file__).parent / "logs"
_LOG_ROOT.mkdir(exist_ok=True)
_LOG_FMT = logging.Formatter("%(asctime)s.%(msecs)03d  %(message)s", datefmt="%H:%M:%S")

IMPORTANT_EVENTS = {
    "session.created",
    "session.updated",
    "input_audio_buffer.speech_started",
    "input_audio_buffer.speech_stopped",
    "conversation.item.input_audio_transcription.completed",
    "response.created",
    "response.function_call_arguments.done",
    "response.audio_transcript.done",
    "response.output_audio_transcript.done",
    "response.done",
    "error",
}

MODEL_ONLY_TOOLS = {"inspect_visual"}
MUTATING_TOOLS = {
    "filter_data",
    "remove_filter",
    "append_visual",
    "highlight_visual",
    "delete_visual",
    "set_low_score_threshold",
}

# ---------------------------------------------------------------------------
# Provider configuration.
# ---------------------------------------------------------------------------
QWEN_API_KEY = (
    os.getenv("QWEN_API_KEY")
    or os.getenv("DASHSCOPE_API_KEY")
    or ""
).strip()

QWEN_REGION = os.getenv("QWEN_REGION", "beijing").strip().lower()
QWEN_WORKSPACE_ID = os.getenv("QWEN_WORKSPACE_ID", "").strip()
QWEN_WS_BASE_OVERRIDE = os.getenv("QWEN_WS_BASE", "").strip()


def _resolve_qwen_ws_base() -> str:
    if QWEN_WS_BASE_OVERRIDE:
        return QWEN_WS_BASE_OVERRIDE
    if QWEN_REGION in {"singapore", "ap-southeast-1"}:
        if QWEN_WORKSPACE_ID:
            return (
                f"wss://{QWEN_WORKSPACE_ID}.ap-southeast-1.maas.aliyuncs.com"
                "/api-ws/v1/realtime"
            )
        # Backward-compatible fallback used by the original Qwen test script.
        return "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
    return "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"


QWEN_WS_BASE = _resolve_qwen_ws_base()

QWEN_MODEL = "qwen3.5-omni-plus-realtime"

# Qwen3.5-Omni-Realtime defaults to Tina. Some older examples use Chelsie,
# but this model rejects Chelsie when it starts generating audio.
QWEN_VOICE = os.getenv("QWEN_REALTIME_VOICE", "Tina").strip()

# Qwen ASR model for input transcription.
QWEN_TRANSCRIPTION_MODEL = os.getenv(
    "QWEN_REALTIME_TRANSCRIPTION_MODEL",
    "qwen3-asr-flash-realtime",
).strip()
QWEN_INPUT_SAMPLE_RATE = int(os.getenv("QWEN_REALTIME_INPUT_SAMPLE_RATE", "16000"))
QWEN_OUTPUT_SAMPLE_RATE = int(os.getenv("QWEN_REALTIME_OUTPUT_SAMPLE_RATE", "24000"))
# Qwen native WebSocket uses "pcm"; OpenAI realtime2 originally used a richer
# audio object and older Qwen experiments in this repo used "pcm16".
QWEN_AUDIO_FORMAT = os.getenv("QWEN_REALTIME_AUDIO_FORMAT", "pcm").strip() or "pcm"

ENABLE_INPUT_TRANSCRIPTION = os.getenv(
    "QWEN_REALTIME_INPUT_TRANSCRIPTION", "true"
).lower() in {"1", "true", "yes", "on"}
SEND_INPUT_TRANSCRIPTION_CONFIG = os.getenv(
    "QWEN_REALTIME_SEND_TRANSCRIPTION_CONFIG", "false"
).lower() in {"1", "true", "yes", "on"}

QWEN_OPENING_ENABLED = os.getenv(
    "QWEN_REALTIME_OPENING_ENABLED", "true"
).lower() in {"1", "true", "yes", "on"}


# VerbalVis streams audio through Qwen's native turn detection flow:
# input_audio_buffer.append -> speech_started/stopped -> committed -> response.
QWEN_TURN_DETECTION = "semantic_vad"
INPUT_MODE = "semantic_vad"
QWEN_VAD_THRESHOLD = 0.7
QWEN_VAD_SILENCE_DURATION_MS = 300

BARGE_IN_ENABLED = True


def _build_qwen_url(model: str) -> str:
    return f"{QWEN_WS_BASE}?model={model}"


def _qwen_tool_schemas() -> list[dict[str, Any]]:
    """Convert the working OpenAI realtime2 flat tools to Qwen's function shape."""
    qwen_tools: list[dict[str, Any]] = []
    for tool in TOOL_SCHEMAS:
        nested_function = tool.get("function")
        function = nested_function if isinstance(nested_function, dict) else tool
        description = function.get("description", "")
        if isinstance(nested_function, dict):
            qwen_tools.append({
                "type": "function",
                "function": {
                    **function,
                    "description": description,
                    "parameters": _qwen_json_schema(function.get("parameters", {})),
                },
            })
            continue
        qwen_tools.append({
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": description,
                "parameters": _qwen_json_schema(
                    tool.get("parameters", {"type": "object", "properties": {}})
                ),
            },
        })
    return qwen_tools


def _qwen_json_schema(value: Any) -> Any:
    """Normalize JSON Schema features that Qwen Realtime currently rejects."""
    if isinstance(value, list):
        return [_qwen_json_schema(item) for item in value if item is not None]
    if not isinstance(value, dict):
        return value

    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key == "type" and isinstance(item, list):
            non_null_types = [t for t in item if t != "null"]
            normalized[key] = non_null_types[0] if non_null_types else "string"
        elif key == "enum" and isinstance(item, list):
            enum_values = [v for v in item if v is not None]
            if enum_values:
                normalized[key] = enum_values
        else:
            normalized[key] = _qwen_json_schema(item)

    properties = normalized.get("properties")
    if isinstance(properties, dict):
        for prop in properties.values():
            if isinstance(prop, dict) and "type" not in prop and "enum" not in prop:
                prop["type"] = "string"

    return normalized


class QwenRealtimeSession:
    """One session = one frontend client + one Qwen-Omni-Realtime connection."""

    def __init__(
        self,
        client_ws: WebSocket,
        session_id: str = "default",
        model: str | None = None,
        analysis_id: str | None = None,
        reset_views: bool = True,
    ):
        self.client_ws = client_ws
        self.session_id = session_id
        self.analysis_id = safe_log_token(analysis_id) or None
        self.log_scope_id = self.analysis_id or safe_log_token(session_id, "session")
        self.reset_views = reset_views
        self.model = QWEN_MODEL
        self.qwen_ws: Any = None
        self.current_response_id: str | None = None
        self.latest_response_id: str | None = None
        self._playback_response_id: str | None = None
        self._latest_user_turn_id: str | None = None
        self._user_turn_open = False
        self._turn_sequence = 0

        self._running = False
        self._upstream_send_lock = asyncio.Lock()
        self._tool_state_lock = asyncio.Lock()
        self._tool_tasks: set[asyncio.Task] = set()
        self._invalidated_response_ids: set[str] = set()

        self._pending_tool_calls: dict[str, int] = {}
        self._pending_should_respond: dict[str, bool] = {}
        self._response_turn_ids: dict[str, str | None] = {}
        self._responses_with_tool_calls: set[str] = set()
        self._tool_followup_pending = False
        self._session_update_pending = False
        self._session_updated = asyncio.Event()
        self._qwen_ready = False
        self._qwen_generation = 0

        self._last_user_speech_stopped_at: float | None = None
        self._response_metrics: dict[str, dict[str, Any]] = {}
        self._timeline: list[dict[str, Any]] = []
        self._current_assistant_audio_item_id: str | None = None
        self._current_assistant_audio_content_index = 0
        self._current_assistant_audio_generated_ms = 0
        self._assistant_transcript_buffer = ""
        self._last_user_transcript = ""

        self._log_dir: Path | None = None
        self._event_logger: logging.Logger | None = None
        self._tool_logger: logging.Logger | None = None
        self._dashboard_logger: logging.Logger | None = None
        self._bargein_logger: logging.Logger | None = None
        self._connection_logger: logging.Logger | None = None
        self._conversation_logger: logging.Logger | None = None

    # ------------------------------------------------------------------
    # Per-session logging
    # ------------------------------------------------------------------

    def _init_session_loggers(self) -> None:
        if self._log_dir:
            return
        log_dir, log_scope_id = resolve_session_log_dir(
            _LOG_ROOT,
            session_id=self.session_id,
            mode="audio",
            analysis_id=self.analysis_id,
        )
        self._log_dir = log_dir
        self.log_scope_id = log_scope_id

        def _make(name: str) -> logging.Logger:
            logger = logging.getLogger(f"realtime_qwen.{name}.{self.session_id}.{self.log_scope_id}")
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
            logger.handlers.clear()
            fh = logging.FileHandler(log_dir / f"{name}.log", encoding="utf-8")
            fh.setFormatter(_LOG_FMT)
            logger.addHandler(fh)
            return logger

        self._event_logger = _make("realtime_events")
        self._tool_logger = _make("tool_calls")
        self._dashboard_logger = _make("dashboard")
        self._bargein_logger = _make("bargein")
        self._connection_logger = _make("connection")
        self._conversation_logger = _make("conversation")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        activate_state_scope(self.log_scope_id, reset=self.reset_views)
        self._running = True

        await self._send_client({
            "type": "init",
            "session_id": self.session_id,
            "analysis_id": self.log_scope_id,
            "views": get_views_for_frontend(),
            "active_filters": get_active_filters_for_frontend(),
            "mode": "barge_in" if BARGE_IN_ENABLED else "turn_based",
            "input_mode": INPUT_MODE,
            "turn_detection": QWEN_TURN_DETECTION,
            "provider": "qwen",
            "model": self.model,
            "input_audio_rate": QWEN_INPUT_SAMPLE_RATE,
            "output_audio_rate": QWEN_OUTPUT_SAMPLE_RATE,
            "audio_format": QWEN_AUDIO_FORMAT,
        })
        self._log_connection(
            "CLIENT_INIT mode=%s input_mode=%s turn_detection=%s",
            "barge_in" if BARGE_IN_ENABLED else "turn_based",
            INPUT_MODE,
            QWEN_TURN_DETECTION,
        )

        try:
            client_task = asyncio.create_task(
                self._client_to_qwen(), name=f"{self.session_id}:client_to_qwen"
            )
            qwen_task = asyncio.create_task(
                self._qwen_loop(), name=f"{self.session_id}:qwen_loop"
            )
            done, pending = await asyncio.wait(
                {client_task, qwen_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc:
                    self._log_connection("SESSION_TASK_ENDED_WITH_ERROR %s", exc)

            self._running = False
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        except Exception as exc:
            self._log_connection("SESSION_ENDED %s", exc)
            await self._send_client({"type": "error", "message": str(exc)})
        finally:
            self._running = False
            persist_active_state_scope()
            await self._shutdown()

    async def _connect_and_configure_qwen(self) -> None:
        if not QWEN_API_KEY:
            raise RuntimeError("QWEN_API_KEY or DASHSCOPE_API_KEY is not set.")

        url = _build_qwen_url(self.model)
        self._log_connection("CONNECTING_QWEN model=%s url=%s", self.model, url)
        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "X-DashScope-DataInspection": "enable",
        }
        self.qwen_ws = await websockets.connect(
            url,
            additional_headers=headers,
            max_size=2**24,
            ping_interval=20,
            ping_timeout=20,
        )
        self._log_connection("QWEN_CONNECTED")
        self._record_timeline("qwen.connected")
        await self._send_session_update()
        await self._wait_for_session_updated()
        self._log_connection("SESSION_UPDATED")
        self._qwen_ready = True
        await self._send_client({"type": "session_ready"})
        await self._send_opening_response()

    async def _restart_qwen_session(self, reason: str) -> None:
        self._qwen_generation += 1
        self._qwen_ready = False
        self.current_response_id = None
        self.latest_response_id = None
        self._playback_response_id = None
        self._assistant_transcript_buffer = ""
        self._pending_tool_calls.clear()
        self._pending_should_respond.clear()
        self._response_turn_ids.clear()
        self._responses_with_tool_calls.clear()
        self._invalidated_response_ids.clear()
        self._tool_followup_pending = False
        self._latest_user_turn_id = None
        self._user_turn_open = False
        self._turn_sequence = 0
        for task in list(self._tool_tasks):
            task.cancel()
        if self._tool_tasks:
            await asyncio.gather(*self._tool_tasks, return_exceptions=True)
        await self._close_qwen()
        self._log_connection("RESTART_QWEN_SESSION reason=%s generation=%s", reason, self._qwen_generation)
        try:
            await self._connect_and_configure_qwen()
        except Exception:
            self._qwen_ready = False
            await self._close_qwen()
            raise

    async def _qwen_loop(self) -> None:
        while self._running:
            ws = self.qwen_ws
            if not ws or not self._qwen_ready:
                await asyncio.sleep(0.05)
                continue
            try:
                await self._qwen_to_client(ws)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._log_connection("QWEN_RELAY_STOPPED error=%s", exc)
                if self._running:
                    await self._send_client({
                        "type": "error",
                        "message": "Qwen Realtime connection closed. Press Start Mic to create a new session.",
                    })
            finally:
                if self.qwen_ws is ws:
                    self._qwen_ready = False
                    await self._close_qwen()

    async def _shutdown(self) -> None:
        for task in list(self._tool_tasks):
            task.cancel()
        if self._tool_tasks:
            await asyncio.gather(*self._tool_tasks, return_exceptions=True)
        await self._close_qwen()

    async def _close_qwen(self) -> None:
        if self.qwen_ws:
            with contextlib.suppress(Exception):
                await self.qwen_ws.close()
        self.qwen_ws = None

    # ------------------------------------------------------------------
    # Session configuration — Qwen-Omni-Realtime schema
    # ------------------------------------------------------------------
    # Differences from OpenAI GA gpt-realtime-2:
    #   - Flat fields: input_audio_format / output_audio_format / voice live
    #     at session root (not under session.audio.input/output).
    #   - turn_detection lives at session root (not under audio.input).
    #   - input_audio_transcription is not sent by default because current
    #     Qwen server docs describe the ASR model as built-in/non-configurable.
    #   - No `reasoning`, no `truncation`, no `tool_choice`, no
    #     `parallel_tool_calls` (per Qwen docs).
    #   - modalities uses "modalities" key with ["text", "audio"].
    #   - Audio formats are short strings: "pcm" (input 16 kHz mono;
    #     output 24 kHz mono on the server side).

    async def _send_session_update(self) -> None:
        self._session_update_pending = True
        self._session_updated.clear()
        self._record_timeline("session.update.sent")

        payload = {
            "type": "session.update",
            "session": self._build_session_config(),
        }

        if self._event_logger:
            self._event_logger.info(
                "SESSION_UPDATE_SENT\n%s",
                json.dumps(payload, indent=2, ensure_ascii=False),
            )
        self._log_connection(
            "SESSION_UPDATE_SENT turn_detection=%s",
            QWEN_TURN_DETECTION,
        )

        await self._send_qwen(payload)

    def _build_instructions(self) -> str:
        state = json.dumps(
            realtime_state(),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return (
            f"{build_system_prompt()}\n\n"
            "CURRENT DASHBOARD METADATA (use this only to choose a relevant view; "
            "chart values require inspect_visual):\n"
            f"{state}"
        )

    def _build_session_config(self) -> dict[str, Any]:
        session: dict[str, Any] = {
            "modalities": ["text", "audio"],
            "instructions": self._build_instructions(),
            "voice": QWEN_VOICE,
            # OpenAI realtime2 original in realtime.py:
            # audio.input.format = {"type": "audio/pcm", "rate": 24000}
            # audio.output.format = {"type": "audio/pcm", "rate": 24000}
            # Qwen native WebSocket expects short root-level format strings.
            "input_audio_format": QWEN_AUDIO_FORMAT,
            "output_audio_format": QWEN_AUDIO_FORMAT,
            # OpenAI realtime2 original: "tools": TOOL_SCHEMAS
            # Qwen requires {"type":"function","function":{...}} wrappers.
            "tools": _qwen_tool_schemas(),
        }

        session["turn_detection"] = {
            "type": "semantic_vad",
            "threshold": QWEN_VAD_THRESHOLD,
            "silence_duration_ms": QWEN_VAD_SILENCE_DURATION_MS,
        }

        if ENABLE_INPUT_TRANSCRIPTION and SEND_INPUT_TRANSCRIPTION_CONFIG:
            # Qwen server events document qwen3-asr-flash-realtime as built-in
            # and not configurable. Keep this opt-in for older compatibility.
            session["input_audio_transcription"] = {
                "model": QWEN_TRANSCRIPTION_MODEL,
            }

        return session

    async def _wait_for_session_updated(self) -> None:
        while self._session_update_pending and self._running:
            raw = await asyncio.wait_for(self.qwen_ws.recv(), timeout=15)
            if self._event_logger:
                self._event_logger.info("SESSION %s", raw[:2000] if len(raw) > 2000 else raw)
            event = json.loads(raw)
            etype = event.get("type", "")
            self._record_timeline(etype)

            if etype == "session.updated":
                self._session_update_pending = False
                self._session_updated.set()
                await self._send_client({
                    "type": "session_updated",
                    "session_id": self.session_id,
                    "analysis_id": self.log_scope_id,
                    "provider": "qwen",
                    "model": self.model,
                    "voice": QWEN_VOICE,
                    "mode": "barge_in" if BARGE_IN_ENABLED else "turn_based",
                    "input_mode": INPUT_MODE,
                    "turn_detection": QWEN_TURN_DETECTION,
                    "input_audio_rate": QWEN_INPUT_SAMPLE_RATE,
                    "output_audio_rate": QWEN_OUTPUT_SAMPLE_RATE,
                    "audio_format": QWEN_AUDIO_FORMAT,
                })
                return

            if etype == "error":
                error = event.get("error", {})
                raise RuntimeError(str(error.get("message", "session.update failed")))

    # ------------------------------------------------------------------
    # Client -> Qwen relay
    # ------------------------------------------------------------------

    async def _client_to_qwen(self) -> None:
        try:
            while self._running:
                raw = await self.client_ws.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "?")

                if self._event_logger:
                    if msg_type == "audio":
                        self._event_logger.debug("CLIENT audio chunk len=%d", len(msg.get("data", "")))
                    else:
                        self._event_logger.info("CLIENT => %s", raw[:500])

                if msg_type == "audio":
                    self._update_analysis_id_from_message(msg)
                    self._init_session_loggers()
                    self._register_client_audio_turn(msg)
                    if not self._qwen_ready:
                        if self._event_logger:
                            self._event_logger.info("CLIENT audio ignored: qwen not ready")
                        continue
                    await self._send_qwen({
                        "type": "input_audio_buffer.append",
                        "audio": msg["data"],
                    })
                elif msg_type == "user_speech_started":
                    self._update_analysis_id_from_message(msg)
                    self._init_session_loggers()
                    await self._begin_user_turn(
                        msg.get("turn_id") or msg.get("turnId"),
                        source="client_vad",
                    )
                elif msg_type == "user_speech_stopped":
                    self._update_analysis_id_from_message(msg)
                    self._init_session_loggers()
                    self._end_user_turn(msg.get("turn_id") or msg.get("turnId"))
                elif msg_type == "truncate_assistant_audio":
                    if not self._qwen_ready:
                        continue
                    await self._truncate_assistant_audio(msg.get("assistant_audio") or msg)
                elif msg_type == "start_session":
                    self._update_analysis_id_from_message(msg)
                    self._init_session_loggers()
                    try:
                        await self._restart_qwen_session("client.start_session")
                    except Exception as exc:
                        self._log_connection("START_SESSION_FAILED %s", exc)
                        await self._send_client({"type": "error", "message": str(exc)})
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            self._log_connection("CLIENT_DISCONNECTED")
            self._running = False
        except Exception as exc:
            self._log_connection("CLIENT_RELAY_STOPPED %s", exc)
            self._running = False

    # ------------------------------------------------------------------
    # Qwen -> Client relay
    # ------------------------------------------------------------------

    async def _qwen_to_client(self, ws: Any) -> None:
        async for raw in ws:
            event = json.loads(raw)
            etype = event.get("type", "")

            if self._event_logger:
                self._event_logger.info("%s", raw[:2000] if len(raw) > 2000 else raw)
            if etype in IMPORTANT_EVENTS:
                self._log_connection("IMPORTANT_EVENT %s", etype)

            response_id = self._event_response_id(event)
            self._record_timeline(etype, response_id=response_id)

            if etype == "session.updated":
                self._session_update_pending = False
                self._session_updated.set()
                await self._send_client({
                    "type": "session_updated",
                    "session_id": self.session_id,
                    "analysis_id": self.log_scope_id,
                    "provider": "qwen",
                    "model": self.model,
                    "voice": QWEN_VOICE,
                    "mode": "barge_in" if BARGE_IN_ENABLED else "turn_based",
                    "input_mode": INPUT_MODE,
                    "turn_detection": QWEN_TURN_DETECTION,
                    "input_audio_rate": QWEN_INPUT_SAMPLE_RATE,
                    "output_audio_rate": QWEN_OUTPUT_SAMPLE_RATE,
                    "audio_format": QWEN_AUDIO_FORMAT,
                })

            elif etype == "response.created":
                resp = event.get("response", {})
                new_response_id = resp.get("id")
                if not new_response_id:
                    continue
                response_turn_id = self._latest_user_turn_id
                self.latest_response_id = new_response_id
                self.current_response_id = new_response_id
                self._playback_response_id = new_response_id
                self._response_turn_ids[new_response_id] = response_turn_id
                self._invalidated_response_ids.discard(new_response_id)
                self._start_response_metrics(new_response_id)
                await self._send_client({
                    "type": "assistant_response_started",
                    "response_id": new_response_id,
                    "turn_id": response_turn_id,
                })

            # Qwen uses response.audio.delta. Also accept OpenAI GA's renamed
            # response.output_audio.delta defensively in case of upstream changes.
            elif etype in ("response.audio.delta", "response.output_audio.delta"):
                audio_response_id = self._event_explicit_response_id(event)
                if not audio_response_id:
                    self._record_timeline("audio.delta.dropped_missing_response_id")
                    continue
                if audio_response_id != self.latest_response_id:
                    self._record_timeline(
                        "audio.delta.dropped_not_latest",
                        response_id=audio_response_id,
                        latest_response_id=self.latest_response_id,
                    )
                    continue
                self._track_assistant_audio(event)
                self._playback_response_id = audio_response_id
                self._mark_first_audio(audio_response_id)
                await self._send_client({
                    "type": "audio",
                    "data": event.get("delta", ""),
                    "response_id": audio_response_id,
                    "turn_id": self._response_turn_ids.get(audio_response_id),
                    "item_id": event.get("item_id"),
                    "content_index": event.get("content_index", 0),
                    "sample_rate": QWEN_OUTPUT_SAMPLE_RATE,
                })

            elif etype in ("response.audio_transcript.delta", "response.output_audio_transcript.delta"):
                transcript_response_id = self._event_explicit_response_id(event)
                if not transcript_response_id:
                    self._record_timeline("audio_transcript.delta.dropped_missing_response_id")
                    continue
                if transcript_response_id != self.latest_response_id:
                    self._record_timeline(
                        "audio_transcript.delta.dropped_not_latest",
                        response_id=transcript_response_id,
                        latest_response_id=self.latest_response_id,
                    )
                    continue
                self._assistant_transcript_buffer += event.get("delta", "")
                await self._send_client({
                    "type": "transcript",
                    "role": "assistant",
                    "delta": event.get("delta", ""),
                    "response_id": transcript_response_id,
                    "turn_id": self._response_turn_ids.get(transcript_response_id),
                })

            elif etype == "input_audio_buffer.speech_started":
                await self._handle_qwen_speech_started()

            elif etype == "input_audio_buffer.speech_stopped":
                self._last_user_speech_stopped_at = time.perf_counter()
                self._end_user_turn(self._latest_user_turn_id)
                await self._send_client({
                    "type": "speech_stopped",
                    "turn_id": self._latest_user_turn_id,
                })

            elif etype == "conversation.item.input_audio_transcription.completed":
                transcript = event.get("transcript", "")
                clean_transcript = transcript.strip()
                if clean_transcript:
                    self._last_user_transcript = clean_transcript
                    self._log_conversation("You", clean_transcript)
                    await self._send_client({
                        "type": "transcript",
                        "role": "user",
                        "text": clean_transcript,
                        "turn_id": self._latest_user_turn_id,
                        "utterance_id": self._latest_user_turn_id,
                    })
                elif self._event_logger:
                    self._event_logger.info("EMPTY_TRANSCRIPT_IGNORED")

            elif etype == "response.function_call_arguments.done":
                if self._tool_logger:
                    self._tool_logger.info("TOOL_EVENT %s", json.dumps(event, ensure_ascii=False)[:2000])

                _tool_name = event.get("name", "?")
                _tool_args = event.get("arguments", "{}")
                if self._tool_logger:
                    self._tool_logger.info("TOOL_CALL name=%s args=%s", _tool_name, _tool_args)

                await self._send_client({
                    "type": "suppress_assistant_buffer",
                    "reason": "tool_call",
                    "response_id": response_id,
                    "turn_id": self._response_turn_ids.get(response_id or ""),
                })
                await self._send_client({
                    "type": "tool_call",
                    "name": _tool_name,
                    "arguments": _tool_args,
                    "response_id": response_id,
                    "turn_id": self._response_turn_ids.get(response_id or ""),
                })

                if response_id:
                    self._responses_with_tool_calls.add(response_id)
                    self._pending_tool_calls[response_id] = (
                        self._pending_tool_calls.get(response_id, 0) + 1
                    )

                task = asyncio.create_task(
                    self._handle_tool_call(event, response_id=response_id),
                    name=f"{self.session_id}:tool:{event.get('name', 'unknown')}",
                )
                self._tool_tasks.add(task)
                task.add_done_callback(self._tool_tasks.discard)

            elif etype == "response.done":
                response_payload = event.get("response", {})
                self._finish_response_metrics(response_id, response_payload)
                has_tool_call = bool(response_id and response_id in self._responses_with_tool_calls)
                assistant_text = self._assistant_transcript_buffer.strip()
                response_turn_id = self._response_turn_ids.get(response_id or "")
                if assistant_text and not has_tool_call:
                    self._log_conversation("AI", assistant_text)
                elif has_tool_call and self._event_logger:
                    self._event_logger.info(
                        "SUPPRESSED_PRE_TOOL_TRANSCRIPT response_id=%s text=%s",
                        response_id,
                        assistant_text[:500],
                    )
                self._assistant_transcript_buffer = ""
                if response_id:
                    self._responses_with_tool_calls.discard(response_id)
                    if not has_tool_call:
                        self._response_turn_ids.pop(response_id, None)
                if not response_id or self.current_response_id == response_id:
                    self.current_response_id = None
                    self._current_assistant_audio_item_id = None
                    self._current_assistant_audio_content_index = 0
                    self._current_assistant_audio_generated_ms = 0
                if response_id and self.latest_response_id == response_id:
                    self.latest_response_id = None
                await self._send_client({
                    "type": "response_done",
                    "response_id": response_id,
                    "turn_id": response_turn_id,
                    "metrics": self._response_metrics.get(response_id, {}) if response_id else {},
                })
                if self._tool_followup_pending and self.current_response_id is None:
                    await self._create_response_if_idle("tool.followup.after_response_done")

            elif etype == "error":
                error = event.get("error", {})
                if error.get("code") == "response_cancel_not_active":
                    log.debug("Ignoring stale response.cancel error: %s", event)
                    continue
                if self._event_logger:
                    self._event_logger.error("QWEN_ERROR %s", json.dumps(event, ensure_ascii=False))
                await self._send_client({
                    "type": "error",
                    "message": str(error.get("message", "Unknown error")),
                    "code": error.get("code"),
                    "param": error.get("param"),
                })

    # ------------------------------------------------------------------
    # Helpers — audio bookkeeping
    # ------------------------------------------------------------------

    def _track_assistant_audio(self, event: dict[str, Any]) -> None:
        item_id = event.get("item_id")
        if not item_id:
            return
        if item_id != self._current_assistant_audio_item_id:
            self._current_assistant_audio_item_id = item_id
            self._current_assistant_audio_content_index = int(event.get("content_index") or 0)
            self._current_assistant_audio_generated_ms = 0

        delta = event.get("delta")
        if not delta:
            return
        try:
            byte_count = len(base64.b64decode(delta))
        except Exception:
            return
        bytes_per_ms = max(1.0, (QWEN_OUTPUT_SAMPLE_RATE * 2) / 1000)
        self._current_assistant_audio_generated_ms += round(byte_count / bytes_per_ms)

    async def _create_response_if_idle(self, reason: str) -> bool:
        if self.current_response_id:
            if reason.startswith("tool."):
                self._tool_followup_pending = True
            if self._event_logger:
                self._event_logger.info(
                    "RESPONSE_CREATE_SKIPPED reason=%s active=%s",
                    reason, self.current_response_id,
                )
            self._record_timeline(
                "response.create.skipped",
                reason=reason, response_id=self.current_response_id,
            )
            return False

        self._tool_followup_pending = False
        sent = await self._send_qwen({"type": "response.create"})
        if not sent and reason.startswith("tool."):
            self._tool_followup_pending = True
        return sent

    async def _send_opening_response(self) -> None:
        if not QWEN_OPENING_ENABLED:
            return
        self._record_timeline("opening.response.create")
        if self._event_logger:
            self._event_logger.info("OPENING_RESPONSE_CREATE")
        await self._create_response_if_idle("session.opening")

    async def _truncate_assistant_audio(self, assistant_audio: Any = None) -> None:
        cursor = assistant_audio if isinstance(assistant_audio, dict) else {}
        item_id = (
            cursor.get("item_id")
            or cursor.get("itemId")
            or self._current_assistant_audio_item_id
        )
        if not item_id:
            return

        content_index = cursor.get("content_index", cursor.get("contentIndex"))
        if content_index is None:
            content_index = self._current_assistant_audio_content_index
        audio_end_ms = cursor.get("audio_end_ms", cursor.get("audioEndMs"))
        if audio_end_ms is None:
            audio_end_ms = 0

        try:
            content_index = int(content_index)
            audio_end_ms = max(0, int(round(float(audio_end_ms))))
        except (TypeError, ValueError):
            content_index = self._current_assistant_audio_content_index
            audio_end_ms = 0

        if self._current_assistant_audio_generated_ms:
            audio_end_ms = min(audio_end_ms, self._current_assistant_audio_generated_ms)

        # OpenAI realtime2 original:
        # await self._send_qwen({
        #     "type": "conversation.item.truncate",
        #     "item_id": item_id,
        #     "content_index": content_index,
        #     "audio_end_ms": audio_end_ms,
        # })
        # Qwen native client events do not expose conversation.item.truncate.
        # Playback is stopped on the frontend; Qwen does not expose the
        # OpenAI-style conversation.item.truncate event used by realtime.py.
        self._record_timeline(
            "conversation.item.truncate.skipped_for_qwen",
            item_id=item_id, content_index=content_index, audio_end_ms=audio_end_ms,
        )
        if self._bargein_logger:
            self._bargein_logger.info(
                "TRUNCATE_SKIPPED_QWEN item_id=%s content_index=%s audio_end_ms=%s",
                item_id, content_index, audio_end_ms,
            )
        self._current_assistant_audio_item_id = None
        self._current_assistant_audio_content_index = 0
        self._current_assistant_audio_generated_ms = 0

    async def _handle_qwen_speech_started(self) -> None:
        """Use Qwen semantic VAD as the single source of interruption truth.

        When Qwen reports speech_started while an assistant response is active,
        immediately cancel upstream generation and clear frontend playback. Input
        transcription remains display/log data only; Python does not classify
        backchannels or wait for the completed transcript before interrupting.
        """
        turn_id = self._latest_user_turn_id if self._user_turn_open else None
        await self._begin_user_turn(turn_id, source="qwen_semantic_vad")

    async def _begin_user_turn(self, turn_id: str | None = None, source: str = "unknown") -> str:
        if not turn_id:
            self._turn_sequence += 1
            turn_id = f"voice-turn-{self._turn_sequence}"
        turn_id = safe_log_token(turn_id, f"voice-turn-{self._turn_sequence + 1}")
        if self._user_turn_open and self._latest_user_turn_id == turn_id:
            return turn_id

        self._latest_user_turn_id = turn_id
        self._user_turn_open = True
        interrupted_response_id = (
            self.latest_response_id
            or self.current_response_id
            or self._playback_response_id
        )
        self._record_timeline(
            "speech_started.observed",
            source=source,
            response_id=interrupted_response_id,
            turn_id=turn_id,
        )
        await self._send_client({
            "type": "speech_started",
            "turn_id": turn_id,
            "utterance_id": turn_id,
        })

        if not BARGE_IN_ENABLED or not interrupted_response_id:
            return turn_id

        self._invalidated_response_ids.add(interrupted_response_id)
        self.latest_response_id = None
        self._playback_response_id = None
        self._assistant_transcript_buffer = ""
        self._tool_followup_pending = False

        self._record_timeline(
            "barge_in",
            source=source,
            response_id=interrupted_response_id,
            turn_id=turn_id,
        )
        self._log_connection(
            "BARGE_IN response_id=%s source=%s turn_id=%s",
            interrupted_response_id, source, turn_id,
        )
        if self._bargein_logger:
            self._bargein_logger.info(
                "BARGE_IN response_id=%s source=%s turn_id=%s",
                interrupted_response_id, source, turn_id,
            )

        cancel_sent = await self._send_qwen({"type": "response.cancel"})
        self._record_timeline(
            "response.cancel.sent" if cancel_sent else "response.cancel.failed",
            response_id=interrupted_response_id,
        )

        await self._send_client({
            "type": "assistant_playback_stop",
            "response_id": interrupted_response_id,
            "turn_id": turn_id,
            "reason": f"{source}_speech_started",
            "clear_queue": True,
        })
        return turn_id

    def _end_user_turn(self, turn_id: str | None = None) -> None:
        if turn_id and self._latest_user_turn_id and turn_id != self._latest_user_turn_id:
            return
        self._user_turn_open = False
        self._record_timeline("speech_stopped.observed", turn_id=self._latest_user_turn_id)

    def _register_client_audio_turn(self, msg: dict[str, Any]) -> None:
        turn_id = msg.get("turn_id") or msg.get("turnId")
        if not turn_id:
            return
        turn_id = safe_log_token(turn_id)
        if not turn_id:
            return
        self._latest_user_turn_id = turn_id
        self._user_turn_open = True

    def _response_is_stale(self, response_id: str | None) -> bool:
        if not response_id:
            return False
        if response_id in self._invalidated_response_ids:
            return True
        response_turn_id = self._response_turn_ids.get(response_id)
        return bool(
            response_turn_id
            and self._latest_user_turn_id
            and response_turn_id != self._latest_user_turn_id
        )

    # ------------------------------------------------------------------
    # Tool call handling
    # ------------------------------------------------------------------

    async def _handle_tool_call(self, event: dict, response_id: str | None) -> None:
        self._init_session_loggers()
        tool_name = event.get("name", "")
        call_id = event.get("call_id", "")
        args_str = event.get("arguments", "{}")

        if self._response_is_stale(response_id):
            if self._tool_logger:
                self._tool_logger.info(
                    "TOOL_DROPPED_STALE_BEFORE_EXEC name=%s response_id=%s",
                    tool_name, response_id,
                )
            await self._finalize_tool_call(response_id, False)
            return

        try:
            arguments = json.loads(args_str)
        except json.JSONDecodeError:
            arguments = {}
        arguments = normalize_tool_arguments(
            tool_name,
            arguments,
            user_transcript=self._last_user_transcript,
        )

        should_respond = False
        try:
            if self._tool_logger:
                self._tool_logger.info(
                    "TOOL_START name=%s call_id=%s args=%s",
                    tool_name, call_id, json.dumps(arguments, ensure_ascii=False),
            )
            tool_started_at = time.perf_counter()

            try:
                async with self._tool_state_lock:
                    result = await asyncio.to_thread(execute_tool, tool_name, arguments)
                    tool_duration_ms = round((time.perf_counter() - tool_started_at) * 1000, 2)
                    views = get_views_for_frontend()
                    log_tool_call(
                        session_id=self.session_id,
                        analysis_id=self.log_scope_id,
                        tool_name=tool_name,
                        params=arguments,
                        mode="barge_in" if BARGE_IN_ENABLED else "turn_based",
                        response_id=response_id,
                        call_id=call_id,
                        result_success=result.get("success"),
                        cancelled=False,
                        metrics={
                            "tool_duration_ms": tool_duration_ms,
                            "timeline": self._timeline_snapshot(),
                        },
                        log_dir=self._log_dir,
                    )
            except asyncio.CancelledError:
                if self._tool_logger:
                    self._tool_logger.info("TOOL_CANCELLED name=%s", tool_name)
                raise

            if self._tool_logger:
                self._tool_logger.info(
                    "TOOL_DONE name=%s call_id=%s dur=%.1fms success=%s",
                    tool_name, call_id, tool_duration_ms, result.get("success"),
                )

            if self._response_is_stale(response_id):
                if self._tool_logger:
                    self._tool_logger.info(
                        "TOOL_RESULT_DROPPED_STALE name=%s response_id=%s",
                        tool_name, response_id,
                    )
                should_respond = False
                return

            if tool_name not in MODEL_ONLY_TOOLS:
                await self._send_client({
                    "type": "tool_result",
                    "response_id": response_id,
                    "turn_id": self._response_turn_ids.get(response_id or ""),
                    "call_id": call_id,
                    "duration_ms": tool_duration_ms,
                    **result,
                })

            if tool_name in MUTATING_TOOLS:
                if self._dashboard_logger:
                    self._dashboard_logger.info(
                        "VIEWS_UPDATE tool=%s args=%s",
                        tool_name, json.dumps(arguments, ensure_ascii=False),
                    )
                await self._send_client({
                    "type": "views_update",
                    "turn_id": self._response_turn_ids.get(response_id or ""),
                    "views": views,
                })

            await self._send_qwen({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": self._tool_result_text(result),
                },
            })

            should_respond = True
        finally:
            await self._finalize_tool_call(response_id, should_respond)

    async def _finalize_tool_call(self, response_id: str | None, should_respond: bool) -> None:
        if response_id is None:
            if should_respond:
                await self._create_response_if_idle("tool.finalize.no_response_id")
            return

        async with self._tool_state_lock:
            remaining = self._pending_tool_calls.get(response_id, 1) - 1
            if remaining <= 0:
                self._pending_tool_calls.pop(response_id, None)
                pending_flag = self._pending_should_respond.pop(response_id, False)
                fire = should_respond or pending_flag
            else:
                self._pending_tool_calls[response_id] = remaining
                if should_respond:
                    self._pending_should_respond[response_id] = True
                fire = False

        if fire:
            await self._create_response_if_idle("tool.finalize")
            self._response_turn_ids.pop(response_id, None)

    def _tool_result_text(
        self,
        result: dict[str, Any],
    ) -> str:
        if result.get("tool") == "inspect_visual":
            return json.dumps(
                {
                    "success": result.get("success", False),
                    "tool": "inspect_visual",
                    "visual": result.get("payload"),
                    "error": result.get("error"),
                },
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )

        payload = {
            "success": result.get("success", False),
            "tool": result.get("tool"),
            "result": self._compact_tool_payload(result),
            "state": realtime_state(),
        }
        if result.get("error"):
            payload["error"] = result["error"]
        if result.get("warning"):
            payload["warning"] = result["warning"]
        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )

    def _compact_tool_payload(self, result: dict[str, Any]) -> Any:
        payload = result.get("payload")
        tool = result.get("tool")
        if not isinstance(payload, dict):
            return {"tool": tool}

        if tool == "inspect_visual":
            return payload

        if tool == "append_visual":
            return {
                "tool": "append_visual",
                "view_id": payload.get("view_id"),
                "title": payload.get("title"),
                "chart_type": payload.get("chart_type"),
                "x": payload.get("x"),
                "y": payload.get("y"),
                "color": payload.get("color"),
            }

        if tool == "filter_data":
            return {
                "tool": "filter_data",
                "filtered_rows": payload.get("filtered_rows"),
                "active_filters": payload.get("active_filters", []),
            }

        if tool == "set_low_score_threshold":
            return {
                "tool": "set_low_score_threshold",
                "low_score_threshold": payload.get("low_score_threshold"),
                "definition": payload.get("definition"),
            }

        if tool == "remove_filter":
            return {
                "tool": "remove_filter",
                "removed_field": payload.get("removed_field"),
                "filtered_rows": payload.get("filtered_rows"),
            }

        if tool == "highlight_visual":
            return {
                "tool": "highlight_visual",
                "view_ids": (
                    payload.get("view_ids")
                    or ([payload.get("view_id")] if payload.get("view_id") else [])
                ),
            }

        if tool == "delete_visual":
            return {
                "tool": "delete_visual",
                "deleted_view_id": (
                    payload.get("deleted_view_id")
                    or payload.get("view_id")
                ),
            }

        return {"tool": tool}

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _event_response_id(self, event: dict[str, Any]) -> str | None:
        response = event.get("response")
        if isinstance(response, dict):
            return response.get("id")
        return event.get("response_id") or self.current_response_id

    def _event_explicit_response_id(self, event: dict[str, Any]) -> str | None:
        response = event.get("response")
        if isinstance(response, dict):
            return response.get("id")
        return event.get("response_id")

    def _start_response_metrics(self, response_id: str | None) -> None:
        if not response_id:
            return
        now = time.perf_counter()
        start_at = self._last_user_speech_stopped_at
        self._response_metrics[response_id] = {
            "response_id": response_id,
            "created_at": now,
            "turn_start_to_response_created_ms": round((now - start_at) * 1000, 2) if start_at else None,
        }

    def _mark_first_audio(self, response_id: str | None) -> None:
        if not response_id:
            return
        metrics = self._response_metrics.setdefault(response_id, {"response_id": response_id})
        if "first_audio_at" in metrics:
            return
        now = time.perf_counter()
        metrics["first_audio_at"] = now
        start_at = self._last_user_speech_stopped_at or metrics.get("created_at")
        metrics["ttfa_ms"] = round((now - start_at) * 1000, 2) if start_at else None
        metrics["response_created_to_first_audio_ms"] = (
            round((now - metrics["created_at"]) * 1000, 2)
            if metrics.get("created_at") else None
        )

    def _finish_response_metrics(self, response_id: str | None, response: dict[str, Any] | None = None) -> None:
        if not response_id:
            return
        metrics = self._response_metrics.setdefault(response_id, {"response_id": response_id})
        now = time.perf_counter()
        metrics["done_at"] = now
        if metrics.get("created_at"):
            metrics["response_duration_ms"] = round((now - metrics["created_at"]) * 1000, 2)
        metrics["invalidated"] = response_id in self._invalidated_response_ids
        response = response or {}
        usage = response.get("usage") or {}
        if usage:
            input_details = usage.get("input_token_details") or {}
            output_details = usage.get("output_token_details") or {}
            metrics["usage"] = {
                "total_tokens": usage.get("total_tokens"),
                "input_tokens": usage.get("input_tokens"),
                "output_tokens": usage.get("output_tokens"),
                "text_input_tokens": input_details.get("text_tokens"),
                "audio_input_tokens": input_details.get("audio_tokens"),
                "cached_input_tokens": input_details.get("cached_tokens"),
                "text_output_tokens": output_details.get("text_tokens"),
                "audio_output_tokens": output_details.get("audio_tokens"),
            }
            if self._event_logger:
                self._event_logger.info(
                    "USAGE response_id=%s usage=%s",
                    response_id, json.dumps(metrics["usage"], ensure_ascii=False),
                )

    def _record_timeline(self, event_type: str, **extra: Any) -> None:
        entry = {
            "t": round(time.perf_counter(), 6),
            "event": event_type,
            **{k: v for k, v in extra.items() if v is not None},
        }
        self._timeline.append(entry)
        if len(self._timeline) > 500:
            self._timeline = self._timeline[-500:]

    def _timeline_snapshot(self) -> list[dict[str, Any]]:
        return self._timeline[-80:]

    def _log_connection(self, message: str, *args: Any) -> None:
        if self._connection_logger:
            self._connection_logger.info(message, *args)

    def _log_conversation(self, role: str, text: str) -> None:
        text = (text or "").strip()
        if text and role.lower() in {"you", "user"}:
            self._init_session_loggers()
        if not text or not self._conversation_logger:
            return
        self._conversation_logger.info("%s: %s", role, text)
        if self._log_dir:
            jsonl_path = self._log_dir / "conversation.jsonl"
            with jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "session_id": self.session_id,
                    "analysis_id": self.log_scope_id,
                    "role": role,
                    "text": text,
                }, ensure_ascii=False) + "\n")

    def _update_analysis_id_from_message(self, msg: dict[str, Any]) -> None:
        if self._log_dir:
            return
        analysis_id = safe_log_token(
            msg.get("analysis_id") or msg.get("analysisId")
        )
        if not analysis_id:
            return
        self.analysis_id = analysis_id
        self.log_scope_id = analysis_id

    # ------------------------------------------------------------------
    # Transport helpers
    # ------------------------------------------------------------------

    async def _send_client(self, msg: dict) -> None:
        try:
            await self.client_ws.send_json(msg)
        except Exception as exc:
            log.debug("Failed to send client message: %s", exc)

    async def _send_qwen(self, msg: dict) -> bool:
        if not self.qwen_ws:
            return False
        try:
            async with self._upstream_send_lock:
                await self.qwen_ws.send(json.dumps(msg, ensure_ascii=False))
            return True
        except Exception as exc:
            log.debug("Failed to send Qwen message: %s", exc)
            return False
