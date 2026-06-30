"""
VerbalVis Realtime API manager — Qwen-Omni-Realtime variant.

Bridges the frontend WebSocket and Alibaba DashScope's Qwen-Omni-Realtime
WebSocket. The frontend protocol stays identical to the OpenAI relay
(realtime.py); only the upstream provider differs.

Uses qwen3.5-omni-plus-realtime as the fixed upstream model.
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

from prompts import build_system_prompt
from tools import (
    TOOL_SCHEMAS,
    context_text,
    execute_tool,
    get_views_for_frontend,
    init_views,
    log_tool_call,
    normalize_tool_arguments,
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

QWEN_RECONNECT_ATTEMPTS = int(os.getenv("QWEN_REALTIME_RECONNECT_ATTEMPTS", "2"))
QWEN_OPENING_ENABLED = os.getenv(
    "QWEN_REALTIME_OPENING_ENABLED", "true"
).lower() in {"1", "true", "yes", "on"}

# VerbalVis uses Qwen's native server VAD flow:
# input_audio_buffer.append -> speech_started/stopped -> committed -> response.
INPUT_MODE = "server_vad"
QWEN_VAD_THRESHOLD = float(os.getenv("QWEN_REALTIME_VAD_THRESHOLD", "0.5"))
QWEN_VAD_PREFIX_PADDING_MS = int(os.getenv("QWEN_REALTIME_VAD_PREFIX_PADDING_MS", "300"))
QWEN_VAD_SILENCE_DURATION_MS = int(os.getenv("QWEN_REALTIME_VAD_SILENCE_DURATION_MS", "800"))

BARGE_IN_ENABLED = os.getenv(
    "VERBALVIS_BARGE_IN_ENABLED", "true"
).lower() not in {"0", "false", "no", "off"}


def _build_qwen_url(model: str) -> str:
    return f"{QWEN_WS_BASE}?model={model}"


def _qwen_tool_schemas() -> list[dict[str, Any]]:
    """Convert the working OpenAI realtime2 flat tools to Qwen's function shape."""
    qwen_tools: list[dict[str, Any]] = []
    for tool in TOOL_SCHEMAS:
        function = tool.get("function") if "function" in tool else tool
        if "function" in tool:
            qwen_tools.append({
                "type": "function",
                "function": {
                    **function,
                    "parameters": _qwen_json_schema(function.get("parameters", {})),
                },
            })
            continue
        qwen_tools.append({
            "type": "function",
            "function": {
                "name": tool.get("name"),
                "description": tool.get("description", ""),
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

    def __init__(self, client_ws: WebSocket, session_id: str = "default", model: str | None = None):
        self.client_ws = client_ws
        self.session_id = session_id
        self.model = QWEN_MODEL
        self.qwen_ws: Any = None
        self.current_response_id: str | None = None

        self._running = False
        self._upstream_send_lock = asyncio.Lock()
        self._tool_state_lock = asyncio.Lock()
        self._tool_tasks: set[asyncio.Task] = set()
        self._invalidated_response_ids: set[str] = set()
        self._turn_epoch = 0

        self._pending_tool_calls: dict[str, int] = {}
        self._pending_should_respond: dict[str, bool] = {}
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
        self._dashboard_context = ""

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
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = _LOG_ROOT / f"{ts}_{self.session_id}_qwen"
        log_dir.mkdir(parents=True, exist_ok=True)
        self._log_dir = log_dir

        def _make(name: str) -> logging.Logger:
            logger = logging.getLogger(f"realtime_qwen.{name}.{self.session_id}.{ts}")
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
        self._init_session_loggers()
        init_views()
        self._dashboard_context = context_text()
        self._running = True

        await self._send_client({
            "type": "init",
            "views": get_views_for_frontend(),
            "mode": "barge_in" if BARGE_IN_ENABLED else "turn_based",
            "input_mode": INPUT_MODE,
            "provider": "qwen",
            "model": self.model,
            "input_audio_rate": QWEN_INPUT_SAMPLE_RATE,
            "output_audio_rate": QWEN_OUTPUT_SAMPLE_RATE,
            "audio_format": QWEN_AUDIO_FORMAT,
        })

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
        self._assistant_transcript_buffer = ""
        self._pending_tool_calls.clear()
        self._pending_should_respond.clear()
        self._invalidated_response_ids.clear()
        for task in list(self._tool_tasks):
            task.cancel()
        if self._tool_tasks:
            await asyncio.gather(*self._tool_tasks, return_exceptions=True)
        await self._close_qwen()
        self._dashboard_context = context_text()
        self._log_connection("RESTART_QWEN_SESSION reason=%s generation=%s", reason, self._qwen_generation)
        try:
            await self._connect_and_configure_qwen()
            await self._inject_context(self._dashboard_context)
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
        self._log_connection("SESSION_UPDATE_SENT")

        await self._send_qwen(payload)

    def _build_instructions(self) -> str:
        if not self._dashboard_context:
            return build_system_prompt()
        return (
            f"{build_system_prompt()}\n\n"
            "CURRENT DASHBOARD CONTEXT (authoritative, refreshes after each tool call):\n"
            f"{self._dashboard_context}"
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
            "type": "server_vad",
            "threshold": QWEN_VAD_THRESHOLD,
            "prefix_padding_ms": QWEN_VAD_PREFIX_PADDING_MS,
            "silence_duration_ms": QWEN_VAD_SILENCE_DURATION_MS,
            "create_response": True,
            "interrupt_response": BARGE_IN_ENABLED,
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
                    "provider": "qwen",
                    "model": self.model,
                    "voice": QWEN_VOICE,
                    "mode": "barge_in" if BARGE_IN_ENABLED else "turn_based",
                    "input_mode": INPUT_MODE,
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
                    if not self._qwen_ready:
                        if self._event_logger:
                            self._event_logger.info("CLIENT audio ignored: qwen not ready")
                        continue
                    await self._send_qwen({
                        "type": "input_audio_buffer.append",
                        "audio": msg["data"],
                    })
                elif msg_type == "truncate_assistant_audio":
                    if not self._qwen_ready:
                        continue
                    await self._truncate_assistant_audio(msg.get("assistant_audio") or msg)
                elif msg_type == "start_session":
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
                    "provider": "qwen",
                    "model": self.model,
                    "voice": QWEN_VOICE,
                    "mode": "barge_in" if BARGE_IN_ENABLED else "turn_based",
                    "input_mode": INPUT_MODE,
                    "input_audio_rate": QWEN_INPUT_SAMPLE_RATE,
                    "output_audio_rate": QWEN_OUTPUT_SAMPLE_RATE,
                    "audio_format": QWEN_AUDIO_FORMAT,
                })

            elif etype == "response.created":
                resp = event.get("response", {})
                self.current_response_id = resp.get("id")
                self._start_response_metrics(self.current_response_id)

            # Qwen uses response.audio.delta. Also accept OpenAI GA's renamed
            # response.output_audio.delta defensively in case of upstream changes.
            elif etype in ("response.audio.delta", "response.output_audio.delta"):
                self._track_assistant_audio(event)
                self._mark_first_audio(response_id)
                await self._send_client({
                    "type": "audio",
                    "data": event.get("delta", ""),
                    "item_id": event.get("item_id"),
                    "content_index": event.get("content_index", 0),
                    "sample_rate": QWEN_OUTPUT_SAMPLE_RATE,
                })

            elif etype in ("response.audio_transcript.delta", "response.output_audio_transcript.delta"):
                self._assistant_transcript_buffer += event.get("delta", "")
                await self._send_client({
                    "type": "transcript",
                    "role": "assistant",
                    "delta": event.get("delta", ""),
                })

            elif etype == "input_audio_buffer.speech_started":
                await self._handle_speech_started()

            elif etype == "input_audio_buffer.speech_stopped":
                self._last_user_speech_stopped_at = time.perf_counter()
                await self._send_client({"type": "speech_stopped"})

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
                    "type": "tool_call",
                    "name": _tool_name,
                    "arguments": _tool_args,
                })

                if response_id:
                    self._pending_tool_calls[response_id] = (
                        self._pending_tool_calls.get(response_id, 0) + 1
                    )

                task = asyncio.create_task(
                    self._handle_tool_call(event, response_id=response_id, turn_epoch=self._turn_epoch),
                    name=f"{self.session_id}:tool:{event.get('name', 'unknown')}",
                )
                self._tool_tasks.add(task)
                task.add_done_callback(self._tool_tasks.discard)

            elif etype == "response.done":
                self._finish_response_metrics(response_id, event.get("response", {}))
                if self._assistant_transcript_buffer.strip():
                    self._log_conversation("AI", self._assistant_transcript_buffer.strip())
                self._assistant_transcript_buffer = ""
                self.current_response_id = None
                self._current_assistant_audio_item_id = None
                self._current_assistant_audio_content_index = 0
                self._current_assistant_audio_generated_ms = 0
                await self._send_client({
                    "type": "response_done",
                    "metrics": self._response_metrics.get(response_id, {}) if response_id else {},
                })

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
        await self._send_qwen({"type": "response.create"})
        return True

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
        # Playback is stopped on the frontend, and response.cancel is sent by
        # _invalidate_current_response when an active response exists.
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

    async def _handle_speech_started(self) -> None:
        # OpenAI realtime2 original used send_cancel=False because GA server VAD
        # handles interruption. Qwen exposes response.cancel but not truncate, so
        # cancel the active response on server-side speech start.
        await self._invalidate_current_response(source="speech_started", send_cancel=True)

    async def _invalidate_current_response(self, source: str, send_cancel: bool) -> None:
        self._turn_epoch += 1
        invalidated_response_id = self.current_response_id
        if invalidated_response_id:
            self._invalidated_response_ids.add(invalidated_response_id)

        self._log_connection(
            "BARGE_IN source=%s invalidated=%s", source, invalidated_response_id
        )
        if self._bargein_logger:
            self._bargein_logger.info(
                "BARGE_IN source=%s invalidated=%s epoch=%d",
                source, invalidated_response_id, self._turn_epoch,
            )
        self._assistant_transcript_buffer = ""
        self._record_timeline("barge_in", source=source, response_id=invalidated_response_id)

        for task in list(self._tool_tasks):
            task.cancel()

        if send_cancel and invalidated_response_id:
            await self._send_qwen({"type": "response.cancel"})

        await self._send_client({
            "type": "speech_started",
            "invalidated_response_id": invalidated_response_id,
        })

    # ------------------------------------------------------------------
    # Tool call handling
    # ------------------------------------------------------------------

    async def _handle_tool_call(self, event: dict, response_id: str | None, turn_epoch: int) -> None:
        tool_name = event.get("name", "")
        call_id = event.get("call_id", "")
        args_str = event.get("arguments", "{}")

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
            if self._is_stale_tool_call(response_id, turn_epoch):
                if self._tool_logger:
                    self._tool_logger.info(
                        "TOOL_STALE_BEFORE_START name=%s args=%s",
                        tool_name, json.dumps(arguments, ensure_ascii=False),
                    )
                return

            if self._tool_logger:
                self._tool_logger.info(
                    "TOOL_START name=%s call_id=%s args=%s",
                    tool_name, call_id, json.dumps(arguments, ensure_ascii=False),
                )
            tool_started_at = time.perf_counter()
            stale_after_execution = False

            try:
                async with self._tool_state_lock:
                    if self._is_stale_tool_call(response_id, turn_epoch):
                        if self._tool_logger:
                            self._tool_logger.info(
                                "TOOL_STALE_AFTER_LOCK name=%s args=%s",
                                tool_name, json.dumps(arguments, ensure_ascii=False),
                            )
                        return

                    result = await asyncio.to_thread(execute_tool, tool_name, arguments)
                    tool_duration_ms = round((time.perf_counter() - tool_started_at) * 1000, 2)
                    stale_after_execution = self._is_stale_tool_call(response_id, turn_epoch)
                    views = get_views_for_frontend()
                    updated_context = context_text()
                    log_tool_call(
                        session_id=self.session_id,
                        tool_name=tool_name,
                        params=arguments,
                        mode="barge_in" if BARGE_IN_ENABLED else "turn_based",
                        response_id=response_id,
                        call_id=call_id,
                        result_success=result.get("success"),
                        cancelled=stale_after_execution,
                        metrics={
                            "tool_duration_ms": tool_duration_ms,
                            "turn_epoch": turn_epoch,
                            "timeline": self._timeline_snapshot(),
                        },
                        log_dir=self._log_dir,
                    )
            except asyncio.CancelledError:
                if self._tool_logger:
                    self._tool_logger.info("TOOL_CANCELLED name=%s", tool_name)
                raise

            if stale_after_execution:
                if self._tool_logger:
                    self._tool_logger.info(
                        "TOOL_STALE name=%s call_id=%s dur=%.1fms",
                        tool_name, call_id, tool_duration_ms,
                    )
                return

            if self._tool_logger:
                self._tool_logger.info(
                    "TOOL_DONE name=%s call_id=%s dur=%.1fms success=%s",
                    tool_name, call_id, tool_duration_ms, result.get("success"),
                )

            await self._send_client({
                "type": "tool_result",
                "response_id": response_id,
                "call_id": call_id,
                "duration_ms": tool_duration_ms,
                **result,
            })

            if tool_name in ("filter_data", "remove_filter", "append_visual", "delete_visual"):
                if self._dashboard_logger:
                    self._dashboard_logger.info(
                        "VIEWS_UPDATE tool=%s args=%s",
                        tool_name, json.dumps(arguments, ensure_ascii=False),
                    )
                await self._send_client({"type": "views_update", "views": views})

            await self._send_qwen({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    # OpenAI realtime2 original:
                    # "output": self._tool_result_text(result, tool_duration_ms),
                    # Qwen only supports function_call_output items here, so
                    # include the refreshed dashboard context inside that output.
                    "output": self._tool_result_text(
                        result,
                        tool_duration_ms,
                        dashboard_context=updated_context,
                    ),
                },
            })

            await self._inject_context(updated_context)
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

    def _is_stale_tool_call(self, response_id: str | None, turn_epoch: int) -> bool:
        return (
            turn_epoch != self._turn_epoch
            or (response_id is not None and response_id in self._invalidated_response_ids)
            or not self._running
        )

    def _tool_result_text(
        self,
        result: dict[str, Any],
        duration_ms: float,
        dashboard_context: str | None = None,
    ) -> str:
        payload = {
            "success": result.get("success", False),
            "payload": self._compact_tool_payload(result),
            "error": result.get("error"),
            "warning": result.get("warning"),
            "metrics": {"tool_duration_ms": duration_ms},
        }
        if dashboard_context:
            payload["dashboard_context"] = dashboard_context
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _compact_tool_payload(self, result: dict[str, Any]) -> Any:
        payload = result.get("payload")
        if not isinstance(payload, dict):
            return payload

        tool = result.get("tool")
        if tool == "append_visual":
            compact = {
                key: payload.get(key)
                for key in (
                    "view_id", "chart_type", "x", "y", "color", "title",
                    "statistics", "filtered_rows",
                )
                if key in payload
            }
            data = payload.get("data")
            if isinstance(data, list):
                compact["data_points"] = len(data)
                compact["data_omitted"] = True
            return compact

        if tool == "filter_data":
            return {
                "action": payload.get("action"),
                "active_filters": payload.get("active_filters", []),
                "filtered_rows": payload.get("filtered_rows"),
            }

        if tool == "remove_filter":
            return {
                "removed_field": payload.get("removed_field"),
                "removed_count": payload.get("removed_count"),
                "active_filters": payload.get("active_filters", []),
                "filtered_rows": payload.get("filtered_rows"),
            }

        if tool in {"highlight_visual", "delete_visual"}:
            return payload

        return payload

    # ------------------------------------------------------------------
    # Context injection
    # ------------------------------------------------------------------

    async def _inject_context(self, text: str) -> None:
        self._dashboard_context = text
        self._record_timeline("dashboard_context.updated")
        if self._event_logger:
            self._event_logger.info("DASHBOARD_CONTEXT_UPDATED %s", text[:2000])
        # OpenAI realtime2 original in realtime.py sends:
        # {
        #   "type": "conversation.item.create",
        #   "item": {
        #     "type": "message",
        #     "role": "system",
        #     "content": [{"type": "input_text", "text": text}],
        #   },
        # }
        # Qwen native WebSocket currently documents conversation.item.create
        # only for function_call_output, so dashboard context is placed in
        # initial instructions and in each function_call_output instead.

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def _event_response_id(self, event: dict[str, Any]) -> str | None:
        response = event.get("response")
        if isinstance(response, dict):
            return response.get("id")
        return event.get("response_id") or self.current_response_id

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
        if not text or not self._conversation_logger:
            return
        self._conversation_logger.info("%s: %s", role, text)
        if self._log_dir:
            jsonl_path = self._log_dir / "conversation.jsonl"
            with jsonl_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "session_id": self.session_id,
                    "role": role,
                    "text": text,
                }, ensure_ascii=False) + "\n")

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
