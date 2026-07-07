"""
VerbalVis Realtime API manager — Qwen-Omni-Realtime.

Design implemented here
-----------------------
1. Qwen semantic VAD is the only source of speech-start / barge-in truth.
2. ``response.function_call_arguments.done`` is the logical commit point for a
   tool call. Once committed, the tool is executed in FIFO order even if a
   newer user turn begins.
3. A newer user turn immediately cancels obsolete model generation and stops
   frontend playback, but it does not roll back committed tool calls.
4. Committed tool results are always returned to Qwen and recorded in the
   session transcript. If a newer user turn exists, the obsolete tool follow-up
   speech is suppressed.
5. While a committed tool batch is running, an automatically created response
   for a newer user turn is cancelled and deferred. Once all committed tools
   finish, one ``response.create`` is sent so the model reasons over both the
   latest user utterance and the completed tool results.
6. Multiple tools emitted by one response execute sequentially and lead to at
   most one follow-up response.

The frontend protocol remains backward-compatible with the existing project.
Additional lifecycle events are emitted for a linear transcript:
``tool_execution_committed``, ``tool_execution_started``,
``tool_execution_completed``, and ``tool_batch_completed``.
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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import websockets
from dotenv import load_dotenv
from fastapi import WebSocket, WebSocketDisconnect

from logging_utils import resolve_session_log_dir, safe_log_token
from prompts import build_system_prompt
import tools as dashboard_tools

load_dotenv()
log = logging.getLogger(__name__)

# Public constant imported by backend/main.py.
QWEN_TURN_DETECTION = "semantic_vad"
INPUT_MODE = "semantic_vad"
BARGE_IN_ENABLED = True

# ---------------------------------------------------------------------------
# Tool aliases from the existing project.
# ---------------------------------------------------------------------------
TOOL_SCHEMAS = dashboard_tools.TOOL_SCHEMAS
activate_state_scope = dashboard_tools.activate_state_scope
execute_tool = dashboard_tools.execute_tool
get_active_filters_for_frontend = dashboard_tools.get_active_filters_for_frontend
get_views_for_frontend = dashboard_tools.get_views_for_frontend
log_tool_call = dashboard_tools.log_tool_call
normalize_tool_arguments = dashboard_tools.normalize_tool_arguments
persist_active_state_scope = dashboard_tools.persist_active_state_scope
realtime_state = dashboard_tools.realtime_state

MODEL_ONLY_TOOLS = {"inspect_visual"}
MUTATING_TOOLS = {
    "filter_data",
    "remove_filter",
    "append_visual",
    "highlight_visual",
    "delete_visual",
    "set_low_score_threshold",
    "undo_last_action",
}

# ---------------------------------------------------------------------------
# Per-session logging.
# ---------------------------------------------------------------------------
_LOG_ROOT = Path(__file__).parent / "logs"
_LOG_ROOT.mkdir(exist_ok=True)
_LOG_FMT = logging.Formatter(
    "%(asctime)s.%(msecs)03d  %(message)s",
    datefmt="%H:%M:%S",
)

IMPORTANT_EVENTS = {
    "session.created",
    "session.updated",
    "input_audio_buffer.speech_started",
    "input_audio_buffer.speech_stopped",
    "conversation.item.input_audio_transcription.delta",
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
        return "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
    return "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"


QWEN_WS_BASE = _resolve_qwen_ws_base()
QWEN_MODEL = "qwen3.5-omni-plus-realtime"
QWEN_VOICE = os.getenv("QWEN_REALTIME_VOICE", "Tina").strip()
QWEN_TRANSCRIPTION_MODEL = os.getenv(
    "QWEN_REALTIME_TRANSCRIPTION_MODEL",
    "qwen3-asr-flash-realtime",
).strip()
QWEN_INPUT_SAMPLE_RATE = int(
    os.getenv("QWEN_REALTIME_INPUT_SAMPLE_RATE", "16000")
)
QWEN_OUTPUT_SAMPLE_RATE = int(
    os.getenv("QWEN_REALTIME_OUTPUT_SAMPLE_RATE", "24000")
)
QWEN_AUDIO_FORMAT = (
    os.getenv("QWEN_REALTIME_AUDIO_FORMAT", "pcm").strip() or "pcm"
)

# Official example/default values. They remain environment-configurable so a
# later pilot can tune them without editing source code.
QWEN_VAD_THRESHOLD = float(
    os.getenv("QWEN_REALTIME_VAD_THRESHOLD", "0.5")
)
QWEN_VAD_SILENCE_DURATION_MS = int(
    os.getenv("QWEN_REALTIME_VAD_SILENCE_DURATION_MS", "800")
)
QWEN_OPENING_ENABLED = os.getenv(
    "QWEN_REALTIME_OPENING_ENABLED",
    "true",
).lower() in {"1", "true", "yes", "on"}


def _build_qwen_url(model: str) -> str:
    return f"{QWEN_WS_BASE}?model={model}"


def _qwen_tool_schemas() -> list[dict[str, Any]]:
    """Convert the project's flat tool schemas to Qwen function wrappers."""
    qwen_tools: list[dict[str, Any]] = []
    for tool in TOOL_SCHEMAS:
        nested_function = tool.get("function")
        function = nested_function if isinstance(nested_function, dict) else tool
        description = function.get("description", "")
        qwen_tools.append(
            {
                "type": "function",
                "function": {
                    "name": function.get("name"),
                    "description": description,
                    "parameters": _qwen_json_schema(
                        function.get(
                            "parameters",
                            {"type": "object", "properties": {}},
                        )
                    ),
                },
            }
        )
    return qwen_tools


def _qwen_json_schema(value: Any) -> Any:
    """Remove JSON-Schema constructs rejected by Qwen Realtime."""
    if isinstance(value, list):
        return [_qwen_json_schema(item) for item in value if item is not None]
    if not isinstance(value, dict):
        return value

    normalized: dict[str, Any] = {}
    for key, item in value.items():
        if key == "type" and isinstance(item, list):
            non_null = [entry for entry in item if entry != "null"]
            normalized[key] = non_null[0] if non_null else "string"
        elif key == "enum" and isinstance(item, list):
            enum_values = [entry for entry in item if entry is not None]
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


@dataclass(slots=True)
class CommittedToolCall:
    response_id: str
    item_id: str | None
    call_id: str
    name: str
    arguments_raw: str
    origin_turn_id: str | None
    origin_turn_sequence: int
    user_transcript: str
    committed_at: float = field(default_factory=time.perf_counter)


@dataclass(slots=True)
class CommittedToolBatch:
    response_id: str
    transaction_id: str
    origin_turn_id: str | None
    origin_turn_sequence: int
    calls: list[CommittedToolCall]
    queued_reason: str
    queued_at: float = field(default_factory=time.perf_counter)


class QwenRealtimeSession:
    """One frontend WebSocket plus one Qwen Realtime WebSocket."""

    def __init__(
        self,
        client_ws: WebSocket,
        session_id: str = "default",
        model: str | None = None,
        analysis_id: str | None = None,
        reset_views: bool = True,
    ) -> None:
        self.client_ws = client_ws
        self.session_id = session_id
        self.analysis_id = safe_log_token(analysis_id) or None
        self.log_scope_id = self.analysis_id or safe_log_token(session_id, "session")
        self.reset_views = reset_views
        self.model = QWEN_MODEL

        self.qwen_ws: Any = None
        self._running = False
        self._qwen_ready = False
        self._qwen_generation = 0
        self._session_update_pending = False
        self._session_updated = asyncio.Event()

        self._upstream_send_lock = asyncio.Lock()
        self._tool_state_lock = asyncio.Lock()

        # Active response / turn state.
        self.current_response_id: str | None = None
        self.latest_response_id: str | None = None
        self._playback_response_id: str | None = None
        self._latest_user_turn_id: str | None = None
        self._latest_user_turn_sequence = 0
        self._user_turn_open = False
        self._turn_sequence_fallback = 0

        self._response_turn_ids: dict[str, str | None] = {}
        self._response_turn_sequences: dict[str, int] = {}
        self._invalidated_response_ids: set[str] = set()
        self._barrier_cancelled_response_ids: set[str] = set()

        # A call is committed at function_call_arguments.done. Calls are grouped
        # by their originating response and later executed by one FIFO worker.
        self._pending_calls_by_response: dict[str, list[CommittedToolCall]] = {}
        self._queued_response_ids: set[str] = set()
        self._known_call_ids: set[str] = set()
        self._tool_queue: asyncio.Queue[CommittedToolBatch | None] = asyncio.Queue()
        self._tool_worker_task: asyncio.Task | None = None
        self._tool_work_count = 0
        self._active_tool_batch: CommittedToolBatch | None = None

        # Response coordination.
        self._deferred_latest_response_needed = False
        self._deferred_latest_turn_id: str | None = None
        self._old_tool_followup_needed = False

        # Transcripts and metrics.
        self._last_user_speech_stopped_at: float | None = None
        self._last_user_transcript = ""
        self._user_transcripts_by_turn: dict[str, str] = {}
        self._assistant_transcript_buffers: dict[str, str] = {}
        self._response_metrics: dict[str, dict[str, Any]] = {}
        self._timeline: list[dict[str, Any]] = []

        self._current_assistant_audio_item_id: str | None = None
        self._current_assistant_audio_content_index = 0
        self._current_assistant_audio_generated_ms = 0

        # Session loggers.
        self._log_dir: Path | None = None
        self._event_logger: logging.Logger | None = None
        self._tool_logger: logging.Logger | None = None
        self._dashboard_logger: logging.Logger | None = None
        self._bargein_logger: logging.Logger | None = None
        self._connection_logger: logging.Logger | None = None
        self._conversation_logger: logging.Logger | None = None

    # ------------------------------------------------------------------
    # Logging
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

        def make_logger(name: str) -> logging.Logger:
            logger = logging.getLogger(
                f"realtime_qwen.{name}.{self.session_id}.{self.log_scope_id}"
            )
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
            logger.handlers.clear()
            handler = logging.FileHandler(
                log_dir / f"{name}.log",
                encoding="utf-8",
            )
            handler.setFormatter(_LOG_FMT)
            logger.addHandler(handler)
            return logger

        self._event_logger = make_logger("realtime_events")
        self._tool_logger = make_logger("tool_calls")
        self._dashboard_logger = make_logger("dashboard")
        self._bargein_logger = make_logger("bargein")
        self._connection_logger = make_logger("connection")
        self._conversation_logger = make_logger("conversation")

    def _log_conversation_record(
        self,
        role: str,
        text: str,
        **metadata: Any,
    ) -> None:
        clean_text = str(text or "").strip()
        if clean_text or metadata:
            self._init_session_loggers()
        if not self._conversation_logger:
            return

        if clean_text:
            self._conversation_logger.info("%s: %s", role, clean_text)
        else:
            self._conversation_logger.info(
                "%s: %s",
                role,
                json.dumps(metadata, ensure_ascii=False, default=str),
            )

        if not self._log_dir:
            return
        record = {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "session_id": self.session_id,
            "analysis_id": self.log_scope_id,
            "role": role,
            "text": clean_text,
            **{key: value for key, value in metadata.items() if value is not None},
        }
        with (self._log_dir / "conversation.jsonl").open(
            "a",
            encoding="utf-8",
        ) as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        activate_state_scope(self.log_scope_id, reset=self.reset_views)
        self._running = True
        self._tool_worker_task = asyncio.create_task(
            self._tool_worker(),
            name=f"{self.session_id}:tool_worker",
        )

        await self._send_client(
            {
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
            }
        )

        try:
            client_task = asyncio.create_task(
                self._client_to_qwen(),
                name=f"{self.session_id}:client_to_qwen",
            )
            qwen_task = asyncio.create_task(
                self._qwen_loop(),
                name=f"{self.session_id}:qwen_loop",
            )
            done, pending = await asyncio.wait(
                {client_task, qwen_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in done:
                if not task.cancelled() and task.exception():
                    self._log_connection(
                        "SESSION_TASK_ENDED_WITH_ERROR %s",
                        task.exception(),
                    )
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
        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "X-DashScope-DataInspection": "enable",
        }
        self._log_connection("CONNECTING_QWEN model=%s url=%s", self.model, url)
        self.qwen_ws = await websockets.connect(
            url,
            additional_headers=headers,
            max_size=2**24,
            ping_interval=20,
            ping_timeout=20,
        )
        self._record_timeline("qwen.connected")
        await self._send_session_update()
        await self._wait_for_session_updated()
        self._qwen_ready = True
        await self._send_client({"type": "session_ready"})
        await self._send_opening_response()

    async def _restart_qwen_session(self, reason: str) -> None:
        if self._tool_work_count:
            await self._send_client(
                {
                    "type": "error",
                    "message": "Cannot restart the realtime session while committed tools are running.",
                }
            )
            return

        self._qwen_generation += 1
        self._qwen_ready = False
        self.current_response_id = None
        self.latest_response_id = None
        self._playback_response_id = None
        self._response_turn_ids.clear()
        self._response_turn_sequences.clear()
        self._invalidated_response_ids.clear()
        self._barrier_cancelled_response_ids.clear()
        self._pending_calls_by_response.clear()
        self._queued_response_ids.clear()
        self._known_call_ids.clear()
        self._deferred_latest_response_needed = False
        self._deferred_latest_turn_id = None
        self._old_tool_followup_needed = False
        self._latest_user_turn_id = None
        self._latest_user_turn_sequence = 0
        self._user_turn_open = False
        self._assistant_transcript_buffers.clear()
        await self._close_qwen()
        self._log_connection(
            "RESTART_QWEN_SESSION reason=%s generation=%s",
            reason,
            self._qwen_generation,
        )
        await self._connect_and_configure_qwen()

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
                    await self._send_client(
                        {
                            "type": "error",
                            "message": (
                                "Qwen Realtime connection closed. "
                                "Press Start Mic to create a new session."
                            ),
                        }
                    )
            finally:
                if self.qwen_ws is ws:
                    self._qwen_ready = False
                    await self._close_qwen()

    async def _shutdown(self) -> None:
        if self._tool_worker_task:
            # Give already committed tools a short opportunity to finish so their
            # dashboard state remains linear even when the browser disconnects.
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._tool_queue.join(), timeout=10)
            await self._tool_queue.put(None)
            with contextlib.suppress(asyncio.TimeoutError):
                await asyncio.wait_for(self._tool_worker_task, timeout=2)
            if not self._tool_worker_task.done():
                self._tool_worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._tool_worker_task
        await self._close_qwen()

    async def _close_qwen(self) -> None:
        if self.qwen_ws:
            with contextlib.suppress(Exception):
                await self.qwen_ws.close()
        self.qwen_ws = None

    # ------------------------------------------------------------------
    # Session configuration
    # ------------------------------------------------------------------

    async def _send_session_update(self) -> None:
        self._session_update_pending = True
        self._session_updated.clear()
        payload = {
            "type": "session.update",
            "session": self._build_session_config(),
        }
        if self._event_logger:
            self._event_logger.info(
                "SESSION_UPDATE_SENT\n%s",
                json.dumps(payload, indent=2, ensure_ascii=False),
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
            "RUNTIME COMMITMENT POLICY:\n"
            "- A fully emitted function call is a committed analytical action and will finish.\n"
            "- The newest completed user request is authoritative for subsequent planning.\n"
            "- If the user corrects a parameter, call the appropriate tool with the corrected parameter; "
            "do not narrate the obsolete request.\n"
            "- If the user explicitly asks to undo, use undo_last_action rather than guessing the previous state.\n"
            "- Brief acknowledgements with no analytical request should not modify the dashboard.\n\n"
            "CURRENT DASHBOARD METADATA (use only to choose a view; inspect_visual is required "
            "for chart values):\n"
            f"{state}"
        )

    def _build_session_config(self) -> dict[str, Any]:
        return {
            "modalities": ["text", "audio"],
            "instructions": self._build_instructions(),
            "voice": QWEN_VOICE,
            "input_audio_format": QWEN_AUDIO_FORMAT,
            "output_audio_format": QWEN_AUDIO_FORMAT,
            "input_audio_transcription": {
                "model": QWEN_TRANSCRIPTION_MODEL,
            },
            "tools": _qwen_tool_schemas(),
            "turn_detection": {
                "type": QWEN_TURN_DETECTION,
                "threshold": QWEN_VAD_THRESHOLD,
                "silence_duration_ms": QWEN_VAD_SILENCE_DURATION_MS,
            },
        }

    async def _wait_for_session_updated(self) -> None:
        while self._session_update_pending and self._running:
            raw = await asyncio.wait_for(self.qwen_ws.recv(), timeout=15)
            event = json.loads(raw)
            if self._event_logger:
                self._event_logger.info(
                    "SESSION %s",
                    raw[:2000] if len(raw) > 2000 else raw,
                )
            etype = event.get("type", "")
            self._record_timeline(etype)
            if etype == "session.updated":
                self._session_update_pending = False
                self._session_updated.set()
                await self._send_session_updated_to_client()
                return
            if etype == "error":
                error = event.get("error", {})
                raise RuntimeError(str(error.get("message", "session.update failed")))

    async def _send_session_updated_to_client(self) -> None:
        await self._send_client(
            {
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
                "vad_threshold": QWEN_VAD_THRESHOLD,
                "vad_silence_duration_ms": QWEN_VAD_SILENCE_DURATION_MS,
            }
        )

    # ------------------------------------------------------------------
    # Frontend -> Qwen
    # ------------------------------------------------------------------

    async def _client_to_qwen(self) -> None:
        try:
            while self._running:
                raw = await self.client_ws.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "?")

                if msg_type == "audio":
                    self._update_analysis_id_from_message(msg)
                    self._init_session_loggers()
                    if not self._qwen_ready:
                        continue
                    await self._send_qwen(
                        {
                            "type": "input_audio_buffer.append",
                            "audio": msg["data"],
                        }
                    )
                elif msg_type in {"user_speech_started", "user_speech_stopped"}:
                    # Backward compatibility only. The latest frontend no longer
                    # emits these; semantic VAD is the sole interruption source.
                    if self._event_logger:
                        self._event_logger.info(
                            "IGNORED_CLIENT_VAD_EVENT type=%s",
                            msg_type,
                        )
                elif msg_type == "truncate_assistant_audio":
                    # Qwen does not expose OpenAI's conversation.item.truncate.
                    await self._record_truncate_skipped(
                        msg.get("assistant_audio") or msg
                    )
                elif msg_type == "assistant_playback_completed":
                    completed_response_id = msg.get("response_id") or msg.get("responseId")
                    if (
                        not completed_response_id
                        or completed_response_id == self._playback_response_id
                    ):
                        self._playback_response_id = None
                elif msg_type == "start_session":
                    self._update_analysis_id_from_message(msg)
                    self._init_session_loggers()
                    try:
                        await self._restart_qwen_session("client.start_session")
                    except Exception as exc:
                        self._log_connection("START_SESSION_FAILED %s", exc)
                        await self._send_client(
                            {"type": "error", "message": str(exc)}
                        )
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            self._running = False
        except Exception as exc:
            self._log_connection("CLIENT_RELAY_STOPPED %s", exc)
            self._running = False

    # ------------------------------------------------------------------
    # Qwen -> frontend
    # ------------------------------------------------------------------

    async def _qwen_to_client(self, ws: Any) -> None:
        async for raw in ws:
            event = json.loads(raw)
            etype = event.get("type", "")
            if self._event_logger:
                self._event_logger.info(
                    "%s",
                    raw[:2000] if len(raw) > 2000 else raw,
                )
            if etype in IMPORTANT_EVENTS:
                self._log_connection("IMPORTANT_EVENT %s", etype)

            response_id = self._event_response_id(event)
            self._record_timeline(etype, response_id=response_id)

            if etype == "session.updated":
                self._session_update_pending = False
                self._session_updated.set()
                await self._send_session_updated_to_client()

            elif etype == "response.created":
                await self._handle_response_created(event)

            elif etype in (
                "response.audio.delta",
                "response.output_audio.delta",
            ):
                await self._handle_audio_delta(event)

            elif etype in (
                "response.audio_transcript.delta",
                "response.output_audio_transcript.delta",
            ):
                await self._handle_assistant_transcript_delta(event)

            elif etype == "input_audio_buffer.speech_started":
                await self._handle_qwen_speech_started(event)

            elif etype == "input_audio_buffer.speech_stopped":
                self._last_user_speech_stopped_at = time.perf_counter()
                self._end_user_turn(event.get("item_id") or self._latest_user_turn_id)
                await self._send_client(
                    {
                        "type": "speech_stopped",
                        "turn_id": self._latest_user_turn_id,
                        "item_id": event.get("item_id"),
                    }
                )

            elif etype == "conversation.item.input_audio_transcription.delta":
                await self._handle_user_transcript_delta(event)

            elif etype == "conversation.item.input_audio_transcription.completed":
                await self._handle_user_transcript_completed(event)

            elif etype == "response.function_call_arguments.done":
                await self._commit_tool_call(event, response_id)

            elif etype == "response.done":
                await self._handle_response_done(event, response_id)

            elif etype == "error":
                await self._handle_qwen_error(event)

    async def _handle_response_created(self, event: dict[str, Any]) -> None:
        response = event.get("response") or {}
        response_id = response.get("id")
        if not response_id:
            return

        turn_id = self._latest_user_turn_id
        turn_sequence = self._latest_user_turn_sequence
        self._response_turn_ids[response_id] = turn_id
        self._response_turn_sequences[response_id] = turn_sequence
        self._assistant_transcript_buffers[response_id] = ""
        self._start_response_metrics(response_id)

        # Tool completion barrier: a VAD-triggered response may be created before
        # an earlier committed tool has finished. Cancel it, but remember that the
        # latest user turn still needs one response after all tool outputs arrive.
        if self._tool_work_count > 0:
            self._barrier_cancelled_response_ids.add(response_id)
            self._invalidated_response_ids.add(response_id)
            self._deferred_latest_response_needed = True
            self._deferred_latest_turn_id = turn_id
            self.current_response_id = response_id
            self.latest_response_id = None
            self._record_timeline(
                "response.deferred_for_tool_barrier",
                response_id=response_id,
                turn_id=turn_id,
                tool_work_count=self._tool_work_count,
            )
            await self._send_qwen({"type": "response.cancel"})
            await self._send_client(
                {
                    "type": "assistant_response_deferred",
                    "response_id": response_id,
                    "turn_id": turn_id,
                    "reason": "committed_tool_batch_running",
                }
            )
            return

        self.current_response_id = response_id
        self.latest_response_id = response_id
        self._playback_response_id = response_id
        await self._send_client(
            {
                "type": "assistant_response_started",
                "response_id": response_id,
                "turn_id": turn_id,
            }
        )

    async def _handle_audio_delta(self, event: dict[str, Any]) -> None:
        response_id = self._event_explicit_response_id(event)
        if (
            not response_id
            or response_id != self.latest_response_id
            or response_id in self._invalidated_response_ids
        ):
            return
        self._track_assistant_audio(event)
        self._playback_response_id = response_id
        self._mark_first_audio(response_id)
        await self._send_client(
            {
                "type": "audio",
                "data": event.get("delta", ""),
                "response_id": response_id,
                "turn_id": self._response_turn_ids.get(response_id),
                "item_id": event.get("item_id"),
                "content_index": event.get("content_index", 0),
                "sample_rate": QWEN_OUTPUT_SAMPLE_RATE,
            }
        )

    async def _handle_assistant_transcript_delta(
        self,
        event: dict[str, Any],
    ) -> None:
        response_id = self._event_explicit_response_id(event)
        if (
            not response_id
            or response_id != self.latest_response_id
            or response_id in self._invalidated_response_ids
        ):
            return
        delta = event.get("delta", "")
        self._assistant_transcript_buffers[response_id] = (
            self._assistant_transcript_buffers.get(response_id, "") + delta
        )
        await self._send_client(
            {
                "type": "transcript",
                "role": "assistant",
                "delta": delta,
                "response_id": response_id,
                "turn_id": self._response_turn_ids.get(response_id),
            }
        )

    async def _handle_qwen_speech_started(self, event: dict[str, Any]) -> None:
        turn_id = event.get("item_id")
        await self._begin_user_turn(
            turn_id=turn_id,
            source="qwen_semantic_vad",
        )

    async def _begin_user_turn(
        self,
        turn_id: str | None,
        source: str,
    ) -> str:
        if not turn_id:
            self._turn_sequence_fallback += 1
            turn_id = f"voice-turn-{self._turn_sequence_fallback}"
        turn_id = safe_log_token(
            turn_id,
            f"voice-turn-{self._turn_sequence_fallback + 1}",
        )

        if self._user_turn_open and self._latest_user_turn_id == turn_id:
            return turn_id

        self._latest_user_turn_sequence += 1
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
            turn_sequence=self._latest_user_turn_sequence,
        )
        await self._send_client(
            {
                "type": "speech_started",
                "turn_id": turn_id,
                "utterance_id": turn_id,
                "turn_sequence": self._latest_user_turn_sequence,
            }
        )

        if not BARGE_IN_ENABLED or not interrupted_response_id:
            return turn_id

        # If a full function call was emitted just before interruption, it is
        # already committed. Queue it now rather than relying on response.done.
        await self._enqueue_committed_batch(
            interrupted_response_id,
            reason="barge_in_after_function_call_commit",
        )

        self._invalidated_response_ids.add(interrupted_response_id)
        self.latest_response_id = None
        self._playback_response_id = None

        partial_text = self._assistant_transcript_buffers.get(
            interrupted_response_id,
            "",
        ).strip()
        if partial_text:
            self._log_conversation_record(
                "AI",
                partial_text,
                status="interrupted",
                response_id=interrupted_response_id,
                interrupted_by_turn_id=turn_id,
            )

        cancel_sent = await self._send_qwen({"type": "response.cancel"})
        self._record_timeline(
            "response.cancel.sent" if cancel_sent else "response.cancel.failed",
            response_id=interrupted_response_id,
        )
        await self._send_client(
            {
                "type": "assistant_playback_stop",
                "response_id": interrupted_response_id,
                "turn_id": turn_id,
                "reason": f"{source}_speech_started",
                "clear_queue": True,
            }
        )
        return turn_id

    def _end_user_turn(self, turn_id: str | None = None) -> None:
        if turn_id and self._latest_user_turn_id and turn_id != self._latest_user_turn_id:
            return
        self._user_turn_open = False
        self._record_timeline(
            "speech_stopped.observed",
            turn_id=self._latest_user_turn_id,
        )

    async def _handle_user_transcript_delta(
        self,
        event: dict[str, Any],
    ) -> None:
        turn_id = event.get("item_id") or self._latest_user_turn_id
        preview = f"{event.get('text', '')}{event.get('stash', '')}"
        await self._send_client(
            {
                "type": "transcript",
                "role": "user",
                "text": preview,
                "turn_id": turn_id,
                "utterance_id": turn_id,
                "item_id": event.get("item_id"),
                "status": "partial",
                "completed": False,
            }
        )

    async def _handle_user_transcript_completed(
        self,
        event: dict[str, Any],
    ) -> None:
        clean_transcript = str(event.get("transcript", "")).strip()
        turn_id = event.get("item_id") or self._latest_user_turn_id
        if not clean_transcript:
            return
        self._last_user_transcript = clean_transcript
        if turn_id:
            self._user_transcripts_by_turn[turn_id] = clean_transcript
        self._log_conversation_record(
            "You",
            clean_transcript,
            turn_id=turn_id,
            turn_sequence=self._latest_user_turn_sequence,
        )
        await self._send_client(
            {
                "type": "transcript",
                "role": "user",
                "text": clean_transcript,
                "turn_id": turn_id,
                "utterance_id": turn_id,
                "item_id": event.get("item_id"),
                "status": "completed",
                "completed": True,
            }
        )

    async def _commit_tool_call(
        self,
        event: dict[str, Any],
        response_id: str | None,
    ) -> None:
        if not response_id:
            return
        call_id = str(event.get("call_id") or "").strip()
        if not call_id or call_id in self._known_call_ids:
            return
        self._known_call_ids.add(call_id)

        origin_turn_id = self._response_turn_ids.get(response_id)
        origin_turn_sequence = self._response_turn_sequences.get(
            response_id,
            self._latest_user_turn_sequence,
        )
        call = CommittedToolCall(
            response_id=response_id,
            item_id=event.get("item_id"),
            call_id=call_id,
            name=str(event.get("name") or ""),
            arguments_raw=str(event.get("arguments") or "{}"),
            origin_turn_id=origin_turn_id,
            origin_turn_sequence=origin_turn_sequence,
            user_transcript=(
                self._user_transcripts_by_turn.get(origin_turn_id or "")
                or self._last_user_transcript
            ),
        )
        self._pending_calls_by_response.setdefault(response_id, []).append(call)

        self._log_conversation_record(
            "TOOL",
            f"{call.name}({call.arguments_raw})",
            status="committed",
            response_id=response_id,
            call_id=call_id,
            origin_turn_id=origin_turn_id,
            origin_turn_sequence=origin_turn_sequence,
        )
        await self._send_client(
            {
                "type": "tool_execution_committed",
                "transaction_id": f"txn-{response_id}",
                "response_id": response_id,
                "origin_turn_id": origin_turn_id,
                "origin_turn_sequence": origin_turn_sequence,
                "call_id": call_id,
                "name": call.name,
                "arguments": call.arguments_raw,
                "status": "committed",
            }
        )
        # Compatibility with the current frontend. Deliberately omit turn_id so
        # a committed old call is not rejected by latest-turn filtering.
        await self._send_client(
            {
                "type": "tool_call",
                "response_id": response_id,
                "origin_turn_id": origin_turn_id,
                "call_id": call_id,
                "name": call.name,
                "arguments": call.arguments_raw,
                "committed": True,
            }
        )

        # If the response has already been invalidated by barge-in, do not wait
        # for a possibly delayed/cancelled response.done.
        if response_id in self._invalidated_response_ids:
            await self._enqueue_committed_batch(
                response_id,
                reason="committed_call_on_invalidated_response",
            )

    async def _handle_response_done(
        self,
        event: dict[str, Any],
        response_id: str | None,
    ) -> None:
        response_payload = event.get("response") or {}
        self._finish_response_metrics(response_id, response_payload)
        if not response_id:
            return

        # response.done is authoritative and contains full function_call output
        # items. Recover any call missed because of a transient event gap.
        for output_item in response_payload.get("output") or []:
            if not isinstance(output_item, dict) or output_item.get("type") != "function_call":
                continue
            await self._commit_tool_call(
                {
                    "response_id": response_id,
                    "item_id": output_item.get("id"),
                    "call_id": output_item.get("call_id"),
                    "name": output_item.get("name"),
                    "arguments": output_item.get("arguments", "{}"),
                },
                response_id,
            )

        response_turn_id = self._response_turn_ids.get(response_id)
        assistant_text = self._assistant_transcript_buffers.pop(
            response_id,
            "",
        ).strip()
        was_barrier_cancelled = response_id in self._barrier_cancelled_response_ids
        was_interrupted = response_id in self._invalidated_response_ids

        if assistant_text and not was_barrier_cancelled and not was_interrupted:
            self._log_conversation_record(
                "AI",
                assistant_text,
                status="completed",
                response_id=response_id,
                turn_id=response_turn_id,
            )

        await self._enqueue_committed_batch(
            response_id,
            reason="response_done",
        )

        if self.current_response_id == response_id:
            self.current_response_id = None
        if self.latest_response_id == response_id:
            self.latest_response_id = None
        # Do not clear _playback_response_id here. response.done means Qwen has
        # finished generating audio, but the browser may still have buffered PCM
        # queued for playback. Keeping the id lets a later semantic-VAD
        # speech_started event stop that queued audio immediately.
        self._reset_audio_tracking()

        if was_barrier_cancelled:
            self._barrier_cancelled_response_ids.discard(response_id)
        else:
            await self._send_client(
                {
                    "type": "response_done",
                    "response_id": response_id,
                    "turn_id": response_turn_id,
                    "interrupted": was_interrupted,
                    "metrics": self._response_metrics.get(response_id, {}),
                }
            )

        await self._release_response_barrier()

    async def _handle_qwen_error(self, event: dict[str, Any]) -> None:
        error = event.get("error") or {}
        if error.get("code") == "response_cancel_not_active":
            return
        if self._event_logger:
            self._event_logger.error(
                "QWEN_ERROR %s",
                json.dumps(event, ensure_ascii=False),
            )
        await self._send_client(
            {
                "type": "error",
                "message": str(error.get("message", "Unknown error")),
                "code": error.get("code"),
                "param": error.get("param"),
            }
        )

    # ------------------------------------------------------------------
    # Committed tool queue
    # ------------------------------------------------------------------

    async def _enqueue_committed_batch(
        self,
        response_id: str,
        reason: str,
    ) -> None:
        if response_id in self._queued_response_ids:
            return
        calls = self._pending_calls_by_response.pop(response_id, [])
        if not calls:
            return

        self._queued_response_ids.add(response_id)
        batch = CommittedToolBatch(
            response_id=response_id,
            transaction_id=f"txn-{response_id}",
            origin_turn_id=calls[0].origin_turn_id,
            origin_turn_sequence=calls[0].origin_turn_sequence,
            calls=calls,
            queued_reason=reason,
        )
        self._tool_work_count += 1
        await self._tool_queue.put(batch)
        self._record_timeline(
            "tool_batch.queued",
            response_id=response_id,
            transaction_id=batch.transaction_id,
            call_count=len(calls),
            reason=reason,
        )

    async def _tool_worker(self) -> None:
        while True:
            batch = await self._tool_queue.get()
            if batch is None:
                self._tool_queue.task_done()
                return
            self._active_tool_batch = batch
            try:
                await self._execute_committed_batch(batch)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.exception("Committed tool batch failed: %s", exc)
                await self._send_client(
                    {
                        "type": "error",
                        "message": f"Committed tool batch failed: {exc}",
                    }
                )
            finally:
                self._active_tool_batch = None
                self._tool_work_count = max(0, self._tool_work_count - 1)
                self._tool_queue.task_done()
                await self._release_response_barrier()

    async def _execute_committed_batch(
        self,
        batch: CommittedToolBatch,
    ) -> None:
        mutating_call_exists = any(
            call.name in MUTATING_TOOLS and call.name != "undo_last_action"
            for call in batch.calls
        )
        before_state = None
        snapshot_fn = getattr(
            dashboard_tools,
            "snapshot_dashboard_state",
            None,
        )
        if mutating_call_exists and callable(snapshot_fn):
            before_state = snapshot_fn()

        committed_tools: list[dict[str, Any]] = []
        any_mutation_succeeded = False

        for index, call in enumerate(batch.calls):
            arguments = self._parse_and_normalize_arguments(call)
            await self._send_client(
                {
                    "type": "tool_execution_started",
                    "transaction_id": batch.transaction_id,
                    "response_id": batch.response_id,
                    "origin_turn_id": batch.origin_turn_id,
                    "origin_turn_sequence": batch.origin_turn_sequence,
                    "call_id": call.call_id,
                    "tool_index": index,
                    "tool_count": len(batch.calls),
                    "name": call.name,
                    "arguments": arguments,
                    "status": "running",
                }
            )
            self._log_conversation_record(
                "TOOL",
                f"{call.name}({json.dumps(arguments, ensure_ascii=False)})",
                status="running",
                transaction_id=batch.transaction_id,
                call_id=call.call_id,
            )

            started_at = time.perf_counter()
            async with self._tool_state_lock:
                result = await asyncio.to_thread(
                    execute_tool,
                    call.name,
                    arguments,
                )
                duration_ms = round(
                    (time.perf_counter() - started_at) * 1000,
                    2,
                )
                views = get_views_for_frontend()
                persist_active_state_scope()

            success = bool(result.get("success"))
            if success and call.name in MUTATING_TOOLS:
                any_mutation_succeeded = True
            committed_tools.append(
                {
                    "name": call.name,
                    "arguments": arguments,
                    "call_id": call.call_id,
                    "success": success,
                }
            )

            log_tool_call(
                session_id=self.session_id,
                analysis_id=self.log_scope_id,
                tool_name=call.name,
                params=arguments,
                mode="barge_in" if BARGE_IN_ENABLED else "turn_based",
                response_id=batch.response_id,
                call_id=call.call_id,
                result_success=success,
                cancelled=False,
                metrics={
                    "tool_duration_ms": duration_ms,
                    "transaction_id": batch.transaction_id,
                    "origin_turn_sequence": batch.origin_turn_sequence,
                    "latest_turn_sequence": self._latest_user_turn_sequence,
                    "timeline": self._timeline_snapshot(),
                },
                log_dir=self._log_dir,
            )

            followup_suppressed = (
                self._latest_user_turn_sequence
                > batch.origin_turn_sequence
            )

            # Existing frontend compatibility. No turn_id is included because a
            # committed old action must still update the current dashboard.
            if call.name not in MODEL_ONLY_TOOLS:
                await self._send_client(
                    {
                        "type": "tool_result",
                        "transaction_id": batch.transaction_id,
                        "response_id": batch.response_id,
                        "origin_turn_id": batch.origin_turn_id,
                        "origin_turn_sequence": batch.origin_turn_sequence,
                        "call_id": call.call_id,
                        "duration_ms": duration_ms,
                        "committed": True,
                        "followup_suppressed": followup_suppressed,
                        **result,
                    }
                )

            if call.name in MUTATING_TOOLS:
                if self._dashboard_logger:
                    self._dashboard_logger.info(
                        "VIEWS_UPDATE transaction=%s tool=%s args=%s",
                        batch.transaction_id,
                        call.name,
                        json.dumps(arguments, ensure_ascii=False),
                    )
                await self._send_client(
                    {
                        "type": "views_update",
                        "transaction_id": batch.transaction_id,
                        "origin_turn_id": batch.origin_turn_id,
                        "origin_turn_sequence": batch.origin_turn_sequence,
                        "committed": True,
                        "views": views,
                    }
                )

            # Always close the committed function call in Qwen conversation.
            await self._send_qwen(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": self._tool_result_text(result),
                    },
                }
            )

            await self._send_client(
                {
                    "type": "tool_execution_completed",
                    "transaction_id": batch.transaction_id,
                    "response_id": batch.response_id,
                    "origin_turn_id": batch.origin_turn_id,
                    "origin_turn_sequence": batch.origin_turn_sequence,
                    "call_id": call.call_id,
                    "name": call.name,
                    "arguments": arguments,
                    "status": "completed" if success else "failed",
                    "success": success,
                    "duration_ms": duration_ms,
                    "followup_suppressed": followup_suppressed,
                    "result": self._compact_tool_payload(result),
                    "error": result.get("error"),
                }
            )
            self._log_conversation_record(
                "TOOL",
                f"{call.name} completed",
                status="completed" if success else "failed",
                transaction_id=batch.transaction_id,
                call_id=call.call_id,
                duration_ms=duration_ms,
                followup_suppressed=followup_suppressed,
                result=self._compact_tool_payload(result),
                error=result.get("error"),
            )

        record_transaction_fn = getattr(
            dashboard_tools,
            "record_dashboard_transaction",
            None,
        )
        if (
            before_state is not None
            and any_mutation_succeeded
            and callable(record_transaction_fn)
        ):
            record_transaction_fn(
                before_state=before_state,
                transaction_id=batch.transaction_id,
                turn_id=batch.origin_turn_id,
                response_id=batch.response_id,
                tools=committed_tools,
            )

        followup_suppressed = (
            self._latest_user_turn_sequence
            > batch.origin_turn_sequence
        )
        await self._send_client(
            {
                "type": "tool_batch_completed",
                "transaction_id": batch.transaction_id,
                "response_id": batch.response_id,
                "origin_turn_id": batch.origin_turn_id,
                "origin_turn_sequence": batch.origin_turn_sequence,
                "tool_count": len(batch.calls),
                "followup_suppressed": followup_suppressed,
                "suppression_reason": (
                    "newer_user_turn"
                    if followup_suppressed
                    else None
                ),
            }
        )

        if followup_suppressed:
            self._record_timeline(
                "tool_followup.suppressed",
                transaction_id=batch.transaction_id,
                origin_turn_sequence=batch.origin_turn_sequence,
                latest_turn_sequence=self._latest_user_turn_sequence,
            )
        else:
            self._old_tool_followup_needed = True

    def _parse_and_normalize_arguments(
        self,
        call: CommittedToolCall,
    ) -> dict[str, Any]:
        try:
            arguments = json.loads(call.arguments_raw)
            if not isinstance(arguments, dict):
                arguments = {}
        except json.JSONDecodeError:
            arguments = {}
        return normalize_tool_arguments(
            call.name,
            arguments,
            user_transcript=call.user_transcript,
        )

    async def _release_response_barrier(self) -> None:
        if self._tool_work_count > 0 or self.current_response_id:
            return

        if self._deferred_latest_response_needed:
            self._deferred_latest_response_needed = False
            deferred_turn_id = self._deferred_latest_turn_id
            self._deferred_latest_turn_id = None
            self._old_tool_followup_needed = False
            self._record_timeline(
                "response.create.after_tool_barrier",
                turn_id=deferred_turn_id,
            )
            await self._send_qwen({"type": "response.create"})
            return

        if self._old_tool_followup_needed:
            self._old_tool_followup_needed = False
            self._record_timeline("response.create.after_committed_tools")
            await self._send_qwen({"type": "response.create"})

    async def _create_response_if_idle(self, reason: str) -> bool:
        if self._tool_work_count > 0:
            self._deferred_latest_response_needed = True
            self._deferred_latest_turn_id = self._latest_user_turn_id
            return False
        if self.current_response_id:
            return False
        self._record_timeline("response.create.sent", reason=reason)
        return await self._send_qwen({"type": "response.create"})

    async def _send_opening_response(self) -> None:
        if QWEN_OPENING_ENABLED:
            await self._create_response_if_idle("session.opening")

    # ------------------------------------------------------------------
    # Tool result formatting
    # ------------------------------------------------------------------

    def _tool_result_text(self, result: dict[str, Any]) -> str:
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

        payload: dict[str, Any] = {
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
                "tool": tool,
                "view_id": payload.get("view_id"),
                "title": payload.get("title"),
                "chart_type": payload.get("chart_type"),
                "x": payload.get("x"),
                "y": payload.get("y"),
                "color": payload.get("color"),
            }
        if tool == "filter_data":
            return {
                "tool": tool,
                "filtered_rows": payload.get("filtered_rows"),
                "active_filters": payload.get("active_filters", []),
            }
        if tool == "set_low_score_threshold":
            return {
                "tool": tool,
                "low_score_threshold": payload.get("low_score_threshold"),
                "definition": payload.get("definition"),
            }
        if tool == "remove_filter":
            return {
                "tool": tool,
                "removed_field": payload.get("removed_field"),
                "filtered_rows": payload.get("filtered_rows"),
            }
        if tool == "highlight_visual":
            return {
                "tool": tool,
                "view_ids": (
                    payload.get("view_ids")
                    or ([payload.get("view_id")] if payload.get("view_id") else [])
                ),
            }
        if tool == "delete_visual":
            return {
                "tool": tool,
                "deleted_view_id": (
                    payload.get("deleted_view_id")
                    or payload.get("view_id")
                ),
            }
        if tool == "undo_last_action":
            return {
                "tool": tool,
                "restored_transaction_id": payload.get(
                    "restored_transaction_id"
                ),
                "undone_tools": payload.get("undone_tools", []),
                "active_filters": payload.get("active_filters", []),
                "restored_view_ids": payload.get("restored_view_ids", []),
            }
        return {"tool": tool}

    # ------------------------------------------------------------------
    # Audio bookkeeping
    # ------------------------------------------------------------------

    def _track_assistant_audio(self, event: dict[str, Any]) -> None:
        item_id = event.get("item_id")
        if not item_id:
            return
        if item_id != self._current_assistant_audio_item_id:
            self._current_assistant_audio_item_id = item_id
            self._current_assistant_audio_content_index = int(
                event.get("content_index") or 0
            )
            self._current_assistant_audio_generated_ms = 0
        delta = event.get("delta")
        if not delta:
            return
        try:
            byte_count = len(base64.b64decode(delta))
        except Exception:
            return
        bytes_per_ms = max(1.0, (QWEN_OUTPUT_SAMPLE_RATE * 2) / 1000)
        self._current_assistant_audio_generated_ms += round(
            byte_count / bytes_per_ms
        )

    def _reset_audio_tracking(self) -> None:
        self._current_assistant_audio_item_id = None
        self._current_assistant_audio_content_index = 0
        self._current_assistant_audio_generated_ms = 0

    async def _record_truncate_skipped(self, assistant_audio: Any) -> None:
        cursor = assistant_audio if isinstance(assistant_audio, dict) else {}
        self._record_timeline(
            "conversation.item.truncate.skipped_for_qwen",
            item_id=(
                cursor.get("item_id")
                or cursor.get("itemId")
                or self._current_assistant_audio_item_id
            ),
            content_index=cursor.get("content_index", cursor.get("contentIndex")),
            audio_end_ms=cursor.get("audio_end_ms", cursor.get("audioEndMs")),
        )
        self._reset_audio_tracking()

    # ------------------------------------------------------------------
    # Metrics / transport helpers
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

    def _start_response_metrics(self, response_id: str) -> None:
        now = time.perf_counter()
        start_at = self._last_user_speech_stopped_at
        self._response_metrics[response_id] = {
            "response_id": response_id,
            "created_at": now,
            "turn_start_to_response_created_ms": (
                round((now - start_at) * 1000, 2)
                if start_at
                else None
            ),
        }

    def _mark_first_audio(self, response_id: str) -> None:
        metrics = self._response_metrics.setdefault(
            response_id,
            {"response_id": response_id},
        )
        if "first_audio_at" in metrics:
            return
        now = time.perf_counter()
        metrics["first_audio_at"] = now
        start_at = self._last_user_speech_stopped_at or metrics.get("created_at")
        metrics["ttfa_ms"] = (
            round((now - start_at) * 1000, 2)
            if start_at
            else None
        )
        metrics["response_created_to_first_audio_ms"] = (
            round((now - metrics["created_at"]) * 1000, 2)
            if metrics.get("created_at")
            else None
        )

    def _finish_response_metrics(
        self,
        response_id: str | None,
        response: dict[str, Any] | None = None,
    ) -> None:
        if not response_id:
            return
        metrics = self._response_metrics.setdefault(
            response_id,
            {"response_id": response_id},
        )
        now = time.perf_counter()
        metrics["done_at"] = now
        if metrics.get("created_at"):
            metrics["response_duration_ms"] = round(
                (now - metrics["created_at"]) * 1000,
                2,
            )
        metrics["invalidated"] = response_id in self._invalidated_response_ids

        usage = (response or {}).get("usage") or {}
        if usage:
            # Official Qwen fields are plural: *_tokens_details.
            input_details = usage.get("input_tokens_details") or {}
            output_details = usage.get("output_tokens_details") or {}
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

    def _record_timeline(self, event_type: str, **extra: Any) -> None:
        self._timeline.append(
            {
                "t": round(time.perf_counter(), 6),
                "event": event_type,
                **{
                    key: value
                    for key, value in extra.items()
                    if value is not None
                },
            }
        )
        if len(self._timeline) > 500:
            self._timeline = self._timeline[-500:]

    def _timeline_snapshot(self) -> list[dict[str, Any]]:
        return self._timeline[-80:]

    def _log_connection(self, message: str, *args: Any) -> None:
        if self._connection_logger:
            self._connection_logger.info(message, *args)

    def _update_analysis_id_from_message(self, msg: dict[str, Any]) -> None:
        if self._log_dir:
            return
        analysis_id = safe_log_token(
            msg.get("analysis_id") or msg.get("analysisId")
        )
        if analysis_id:
            self.analysis_id = analysis_id
            self.log_scope_id = analysis_id

    async def _send_client(self, msg: dict[str, Any]) -> None:
        try:
            await self.client_ws.send_json(msg)
        except Exception as exc:
            log.debug("Failed to send client message: %s", exc)

    async def _send_qwen(self, msg: dict[str, Any]) -> bool:
        if not self.qwen_ws:
            return False
        try:
            async with self._upstream_send_lock:
                await self.qwen_ws.send(
                    json.dumps(msg, ensure_ascii=False)
                )
            return True
        except Exception as exc:
            log.debug("Failed to send Qwen message: %s", exc)
            return False
