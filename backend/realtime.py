"""
Minimal Qwen-Omni-Realtime bridge for VerbalVis.

Design goals:
- Follow the official Qwen realtime event flow.
- Keep only one active model response.
- Let Qwen semantic VAD decide when the user starts speaking.
- Execute completed function calls sequentially after response.done.
- Keep the existing VerbalVis dashboard tools and multi-file logs.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import websockets
from dotenv import load_dotenv
from fastapi import WebSocket, WebSocketDisconnect

from logging_utils import resolve_session_log_dir, safe_log_token
from prompts import build_system_prompt
from tools import (
    TOOL_SCHEMAS,
    execute_tool,
    get_views_for_frontend,
    init_views,
    log_tool_call,
    normalize_tool_arguments,
    realtime_state,
)

load_dotenv()

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fixed Qwen configuration
# ---------------------------------------------------------------------------

QWEN_API_KEY = (
    os.getenv("DASHSCOPE_API_KEY")
    or os.getenv("QWEN_API_KEY")
    or ""
).strip()

QWEN_MODEL = "qwen3.5-omni-plus-realtime"
QWEN_VOICE = "Ethan"

QWEN_WS_URL = (
    "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"
    f"?model={QWEN_MODEL}"
)

QWEN_INPUT_SAMPLE_RATE = 16000
QWEN_OUTPUT_SAMPLE_RATE = 24000
QWEN_AUDIO_FORMAT = "pcm"

QWEN_TURN_DETECTION = "semantic_vad"
QWEN_VAD_THRESHOLD = 0.5
QWEN_VAD_PREFIX_PADDING_MS = 500
QWEN_VAD_SILENCE_DURATION_MS = 800

# Tools that change something visible on the dashboard.
DASHBOARD_TOOLS = {
    "filter_data",
    "remove_filter",
    "append_visual",
    "highlight_visual",
    "delete_visual",
    "set_low_score_threshold",
}

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_LOG_ROOT = Path(__file__).parent / "logs"
_LOG_ROOT.mkdir(exist_ok=True)

_LOG_FMT = logging.Formatter(
    "%(asctime)s.%(msecs)03d  %(message)s",
    datefmt="%H:%M:%S",
)


@dataclass
class PendingToolCall:
    call_id: str
    name: str
    arguments_raw: str
    response_id: str | None


def _qwen_json_schema(value: Any) -> Any:
    """
    Remove nullable JSON-Schema constructs that Qwen Realtime may reject.

    The local VerbalVis tool schemas sometimes use:
        {"type": ["string", "null"]}
        {"enum": ["a", "b", None]}

    Qwen works more reliably with the non-null form.
    """
    if isinstance(value, list):
        return [_qwen_json_schema(item) for item in value if item is not None]

    if not isinstance(value, dict):
        return value

    normalized: dict[str, Any] = {}

    for key, item in value.items():
        if key == "type" and isinstance(item, list):
            non_null = [kind for kind in item if kind != "null"]
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
            if (
                isinstance(prop, dict)
                and "type" not in prop
                and "enum" not in prop
            ):
                prop["type"] = "string"

    return normalized


def _qwen_tool_schemas() -> list[dict[str, Any]]:
    """Convert the local flat tool schemas to Qwen function tools."""
    result: list[dict[str, Any]] = []

    for tool in TOOL_SCHEMAS:
        nested = tool.get("function")
        function = nested if isinstance(nested, dict) else tool

        result.append(
            {
                "type": "function",
                "function": {
                    "name": function.get("name"),
                    "description": function.get("description", ""),
                    "parameters": _qwen_json_schema(
                        function.get(
                            "parameters",
                            {"type": "object", "properties": {}},
                        )
                    ),
                },
            }
        )

    return result


class QwenRealtimeSession:
    """
    One browser WebSocket plus one Qwen Realtime WebSocket.

    Runtime state is intentionally small:
    - current_response_id
    - last_user_transcript
    - assistant_transcript
    """

    def __init__(
        self,
        client_ws: WebSocket,
        session_id: str = "default",
        model: str | None = None,
        analysis_id: str | None = None,
    ) -> None:
        self.client_ws = client_ws
        self.session_id = session_id
        self.analysis_id = safe_log_token(analysis_id) or None
        self.log_scope_id = (
            self.analysis_id
            or safe_log_token(session_id, "session")
        )

        # main.py may pass a model, but this implementation is intentionally
        # fixed to the official Qwen realtime model used by this project.
        self.model = QWEN_MODEL

        self.qwen_ws: Any = None
        self.running = False

        self.current_response_id: str | None = None

        self.last_user_transcript = ""
        self.assistant_transcript = ""

        self.last_user_speech_stopped_at: float | None = None
        self.response_created_at: dict[str, float] = {}
        self.first_audio_at: dict[str, float] = {}

        self._send_lock = asyncio.Lock()

        self._log_dir: Path | None = None
        self._event_logger: logging.Logger | None = None
        self._tool_logger: logging.Logger | None = None
        self._dashboard_logger: logging.Logger | None = None
        self._bargein_logger: logging.Logger | None = None
        self._connection_logger: logging.Logger | None = None
        self._conversation_logger: logging.Logger | None = None

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        init_views()
        self._init_session_loggers()
        self.running = True

        await self._send_client(
            {
                "type": "init",
                "session_id": self.session_id,
                "analysis_id": self.log_scope_id,
                "views": get_views_for_frontend(),
                "mode": "barge_in",
                "input_mode": "semantic_vad",
                "turn_detection": QWEN_TURN_DETECTION,
                "provider": "qwen",
                "model": self.model,
                "input_audio_rate": QWEN_INPUT_SAMPLE_RATE,
                "output_audio_rate": QWEN_OUTPUT_SAMPLE_RATE,
                "audio_format": QWEN_AUDIO_FORMAT,
            }
        )

        try:
            await self._connect_qwen()
            await self._configure_qwen_session()

            client_task = asyncio.create_task(
                self._client_to_qwen(),
                name=f"{self.session_id}:client-to-qwen",
            )
            qwen_task = asyncio.create_task(
                self._qwen_to_client(),
                name=f"{self.session_id}:qwen-to-client",
            )

            done, pending = await asyncio.wait(
                {client_task, qwen_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                if task.cancelled():
                    continue
                error = task.exception()
                if error:
                    raise error

            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

        except WebSocketDisconnect:
            self._log_connection("CLIENT_DISCONNECTED")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._log_connection("SESSION_ERROR %s", exc)
            await self._send_client(
                {
                    "type": "error",
                    "message": str(exc),
                }
            )
            raise
        finally:
            self.running = False
            await self._close_qwen()

    # ------------------------------------------------------------------
    # Qwen connection and session configuration
    # ------------------------------------------------------------------

    async def _connect_qwen(self) -> None:
        if not QWEN_API_KEY:
            raise RuntimeError(
                "DASHSCOPE_API_KEY or QWEN_API_KEY is not configured."
            )

        headers = {
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "X-DashScope-DataInspection": "enable",
        }

        self._log_connection(
            "CONNECTING model=%s url=%s",
            self.model,
            QWEN_WS_URL,
        )

        self.qwen_ws = await websockets.connect(
            QWEN_WS_URL,
            additional_headers=headers,
            max_size=2**24,
            ping_interval=20,
            ping_timeout=20,
        )

        self._log_connection("CONNECTED")

    async def _configure_qwen_session(self) -> None:
        payload = {
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": self._build_instructions(),
                "voice": QWEN_VOICE,
                "input_audio_format": QWEN_AUDIO_FORMAT,
                "output_audio_format": QWEN_AUDIO_FORMAT,
                "input_audio_transcription": {
                    "model": "qwen3-asr-flash-realtime",
                },
                "turn_detection": {
                    "type": QWEN_TURN_DETECTION,
                    "threshold": QWEN_VAD_THRESHOLD,
                    "prefix_padding_ms": QWEN_VAD_PREFIX_PADDING_MS,
                    "silence_duration_ms": QWEN_VAD_SILENCE_DURATION_MS,
                },
                "tools": _qwen_tool_schemas(),
            },
        }

        await self._send_qwen(payload)

        while self.running:
            raw = await asyncio.wait_for(
                self.qwen_ws.recv(),
                timeout=20,
            )
            event = json.loads(raw)
            self._log_event(event)

            event_type = event.get("type", "")

            if event_type == "session.updated":
                self._log_connection("SESSION_UPDATED")
                await self._send_client(
                    {
                        "type": "session_updated",
                        "session_id": self.session_id,
                        "analysis_id": self.log_scope_id,
                        "mode": "barge_in",
                        "input_mode": "semantic_vad",
                        "turn_detection": QWEN_TURN_DETECTION,
                        "provider": "qwen",
                        "model": self.model,
                        "voice": QWEN_VOICE,
                        "input_audio_rate": QWEN_INPUT_SAMPLE_RATE,
                        "output_audio_rate": QWEN_OUTPUT_SAMPLE_RATE,
                        "audio_format": QWEN_AUDIO_FORMAT,
                    }
                )
                await self._send_client({"type": "session_ready"})
                return

            if event_type == "error":
                raise RuntimeError(self._error_message(event))

    def _build_instructions(self) -> str:
        state = json.dumps(
            realtime_state(),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return (
            f"{build_system_prompt()}\n\n"
            "CURRENT DASHBOARD METADATA:\n"
            f"{state}"
        )

    # ------------------------------------------------------------------
    # Browser -> Qwen
    # ------------------------------------------------------------------

    async def _client_to_qwen(self) -> None:
        while self.running:
            raw = await self.client_ws.receive_text()
            message = json.loads(raw)
            message_type = message.get("type", "")

            if message_type == "audio":
                audio = message.get("data")
                if audio:
                    await self._send_qwen(
                        {
                            "type": "input_audio_buffer.append",
                            "audio": audio,
                        }
                    )

            elif message_type == "start_session":
                # The Qwen connection is already ready. This keeps old
                # frontends harmless without restarting the upstream session.
                await self._send_client({"type": "session_ready"})

            elif message_type in {"close", "disconnect"}:
                self.running = False
                return

    # ------------------------------------------------------------------
    # Qwen -> Browser
    # ------------------------------------------------------------------

    async def _qwen_to_client(self) -> None:
        async for raw in self.qwen_ws:
            event = json.loads(raw)
            self._log_event(event)

            event_type = event.get("type", "")

            if event_type == "session.updated":
                # A later session update is harmless.
                continue

            if event_type == "response.created":
                await self._handle_response_created(event)
                continue

            if event_type in {
                "response.audio.delta",
                "response.output_audio.delta",
            }:
                await self._handle_audio_delta(event)
                continue

            if event_type in {
                "response.audio_transcript.delta",
                "response.output_audio_transcript.delta",
            }:
                await self._handle_assistant_transcript_delta(event)
                continue

            if event_type in {
                "response.audio_transcript.done",
                "response.output_audio_transcript.done",
            }:
                await self._handle_assistant_transcript_done(event)
                continue

            if event_type in {
                "response.audio.done",
                "response.output_audio.done",
            }:
                self._handle_audio_done(event)
                continue

            if event_type == "input_audio_buffer.speech_started":
                await self._handle_speech_started(event)
                continue

            if event_type == "input_audio_buffer.speech_stopped":
                await self._handle_speech_stopped(event)
                continue

            if event_type == (
                "conversation.item.input_audio_transcription.delta"
            ):
                await self._handle_user_transcript_delta(event)
                continue

            if event_type == (
                "conversation.item.input_audio_transcription.completed"
            ):
                await self._handle_user_transcript_completed(event)
                continue

            if event_type == "response.function_call_arguments.done":
                await self._handle_function_call(event)
                continue

            if event_type == "response.done":
                await self._handle_response_done(event)
                continue

            if event_type == "error":
                await self._handle_error(event)
                continue

    async def _handle_response_created(
        self,
        event: dict[str, Any],
    ) -> None:
        response = event.get("response")
        response_id = (
            response.get("id")
            if isinstance(response, dict)
            else event.get("response_id")
        )

        if not response_id:
            return

        self.current_response_id = response_id
        self.assistant_transcript = ""

        now = time.perf_counter()
        self.response_created_at[response_id] = now

        await self._send_client(
            {
                "type": "assistant_response_started",
                "response_id": response_id,
            }
        )

    async def _handle_audio_delta(
        self,
        event: dict[str, Any],
    ) -> None:
        response_id = self._event_response_id(event)

        # Ignore late audio from a response that was already cancelled.
        if (
            not response_id
            or response_id != self.current_response_id
        ):
            return

        if response_id not in self.first_audio_at:
            now = time.perf_counter()
            self.first_audio_at[response_id] = now

            created_at = self.response_created_at.get(response_id)
            ttfa_ms = (
                round((now - created_at) * 1000, 2)
                if created_at
                else None
            )

            if self._event_logger:
                self._event_logger.info(
                    "FIRST_AUDIO response_id=%s ttfa_ms=%s",
                    response_id,
                    ttfa_ms,
                )

        await self._send_client(
            {
                "type": "audio",
                "data": event.get("delta", ""),
                "response_id": response_id,
                "sample_rate": QWEN_OUTPUT_SAMPLE_RATE,
            }
        )

    async def _handle_assistant_transcript_delta(
        self,
        event: dict[str, Any],
    ) -> None:
        response_id = self._event_response_id(event)

        if (
            not response_id
            or response_id != self.current_response_id
        ):
            return

        delta = event.get("delta", "")
        if not delta:
            return

        self.assistant_transcript += delta

        await self._send_client(
            {
                "type": "transcript",
                "role": "assistant",
                "delta": delta,
                "response_id": response_id,
            }
        )

    async def _handle_assistant_transcript_done(
        self,
        event: dict[str, Any],
    ) -> None:
        response_id = self._event_response_id(event)

        if (
            not response_id
            or response_id != self.current_response_id
        ):
            return

        transcript = str(event.get("transcript") or "").strip()
        if not transcript:
            return

        self.assistant_transcript = transcript

        await self._send_client(
            {
                "type": "assistant_transcript_done",
                "response_id": response_id,
                "text": transcript,
            }
        )

    def _handle_audio_done(
        self,
        event: dict[str, Any],
    ) -> None:
        response_id = self._event_response_id(event)

        if self._event_logger:
            self._event_logger.info(
                "AUDIO_GENERATION_DONE response_id=%s",
                response_id,
            )

    async def _handle_speech_started(
        self,
        event: dict[str, Any],
    ) -> None:
        utterance_id = (
            event.get("item_id")
            or event.get("utterance_id")
        )

        await self._send_client(
            {
                "type": "speech_started",
                "utterance_id": utterance_id,
            }
        )

        response_id = self.current_response_id

        if not response_id:
            return

        self._log_bargein(
            "BARGE_IN response_id=%s utterance_id=%s",
            response_id,
            utterance_id,
        )

        self.current_response_id = None
        self.assistant_transcript = ""

        await self._send_client(
            {
                "type": "assistant_playback_stop",
                "response_id": response_id,
                "reason": "qwen_semantic_vad_speech_started",
                "clear_queue": True,
            }
        )

    async def _handle_speech_stopped(
        self,
        event: dict[str, Any],
    ) -> None:
        self.last_user_speech_stopped_at = time.perf_counter()

        await self._send_client(
            {
                "type": "speech_stopped",
                "utterance_id": (
                    event.get("item_id")
                    or event.get("utterance_id")
                ),
            }
        )

    async def _handle_user_transcript_delta(
        self,
        event: dict[str, Any],
    ) -> None:
        preview = (
            str(event.get("text") or "")
            + str(event.get("stash") or "")
        ).strip()

        if not preview:
            return

        await self._send_client(
            {
                "type": "transcript",
                "role": "user",
                "text": preview,
                "status": "partial",
                "completed": False,
                "utterance_id": event.get("item_id"),
                "language": event.get("language"),
                "emotion": event.get("emotion"),
            }
        )

    async def _handle_user_transcript_completed(
        self,
        event: dict[str, Any],
    ) -> None:
        transcript = str(event.get("transcript") or "").strip()

        if not transcript:
            return

        self.last_user_transcript = transcript
        self._log_conversation("You", transcript)

        await self._send_client(
            {
                "type": "transcript",
                "role": "user",
                "text": transcript,
                "status": "completed",
                "completed": True,
                "utterance_id": event.get("item_id"),
            }
        )

    async def _handle_function_call(
        self,
        event: dict[str, Any],
    ) -> None:
        if self._tool_logger:
            self._tool_logger.info(
                "TOOL_CALL_CREATED response_id=%s call_id=%s "
                "name=%s arguments=%s",
                self._event_response_id(event),
                event.get("call_id"),
                event.get("name"),
                event.get("arguments"),
            )

    async def _handle_response_done(
        self,
        event: dict[str, Any],
    ) -> None:
        response = event.get("response")
        response = response if isinstance(response, dict) else {}

        response_id = str(response.get("id") or "") or None
        status = str(response.get("status") or "")

        was_active = (
            response_id
            and response_id == self.current_response_id
        )

        if was_active:
            self.current_response_id = None

        if status != "completed":
            self.assistant_transcript = ""

            if was_active:
                await self._send_client(
                    {
                        "type": "response_done",
                        "response_id": response_id,
                        "status": status,
                        "metrics": self._response_metrics(
                            response_id,
                            response,
                        ),
                    }
                )
            return

        tool_calls = self._tool_calls_from_response(response)

        if tool_calls:
            self.assistant_transcript = ""
            await self._execute_tool_calls(tool_calls)
            return

        transcript = (
            self.assistant_transcript.strip()
            or self._assistant_transcript_from_response(response)
        )

        if transcript:
            self._log_conversation("AI", transcript)

        self.assistant_transcript = ""

        await self._send_client(
            {
                "type": "response_done",
                "response_id": response_id,
                "status": status,
                "metrics": self._response_metrics(
                    response_id,
                    response,
                ),
            }
        )

    @staticmethod
    def _tool_calls_from_response(
        response: dict[str, Any],
    ) -> list[PendingToolCall]:
        calls: list[PendingToolCall] = []

        response_id = str(response.get("id") or "") or None

        for item in response.get("output") or []:
            if not isinstance(item, dict):
                continue

            if item.get("type") != "function_call":
                continue

            if item.get("status") not in {None, "completed"}:
                continue

            call_id = str(item.get("call_id") or "")
            name = str(item.get("name") or "")

            if not call_id or not name:
                continue

            arguments = item.get("arguments") or "{}"
            if not isinstance(arguments, str):
                arguments = json.dumps(
                    arguments,
                    ensure_ascii=False,
                )

            calls.append(
                PendingToolCall(
                    call_id=call_id,
                    name=name,
                    arguments_raw=arguments,
                    response_id=response_id,
                )
            )

        return calls

    @staticmethod
    def _assistant_transcript_from_response(
        response: dict[str, Any],
    ) -> str:
        parts: list[str] = []

        for item in response.get("output") or []:
            if not isinstance(item, dict):
                continue

            if item.get("type") != "message":
                continue

            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue

                text = (
                    content.get("transcript")
                    or content.get("text")
                    or ""
                )

                if text:
                    parts.append(str(text))

        return "".join(parts).strip()

    async def _execute_tool_calls(
        self,
        calls: list[PendingToolCall],
    ) -> None:
        for pending in calls:
            started_at = time.perf_counter()

            try:
                raw_arguments = json.loads(
                    pending.arguments_raw or "{}"
                )
                if not isinstance(raw_arguments, dict):
                    raw_arguments = {}
            except json.JSONDecodeError:
                raw_arguments = {}

            arguments = normalize_tool_arguments(
                pending.name,
                raw_arguments,
                user_transcript=None,
            )

            await self._send_client(
                {
                    "type": "tool_call",
                    "name": pending.name,
                    "arguments": json.dumps(
                        arguments,
                        ensure_ascii=False,
                    ),
                    "response_id": pending.response_id,
                    "call_id": pending.call_id,
                }
            )

            if self._tool_logger:
                self._tool_logger.info(
                    "TOOL_START name=%s call_id=%s args=%s",
                    pending.name,
                    pending.call_id,
                    json.dumps(arguments, ensure_ascii=False),
                )

            try:
                result = await asyncio.to_thread(
                    execute_tool,
                    pending.name,
                    arguments,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                result = {
                    "success": False,
                    "tool": pending.name,
                    "payload": None,
                    "error": str(exc),
                }

            duration_ms = round(
                (time.perf_counter() - started_at) * 1000,
                2,
            )

            if self._tool_logger:
                self._tool_logger.info(
                    "TOOL_DONE name=%s call_id=%s "
                    "duration_ms=%s success=%s",
                    pending.name,
                    pending.call_id,
                    duration_ms,
                    result.get("success"),
                )

            log_tool_call(
                session_id=self.session_id,
                analysis_id=self.log_scope_id,
                tool_name=pending.name,
                params=arguments,
                mode="barge_in",
                response_id=pending.response_id,
                call_id=pending.call_id,
                result_success=result.get("success"),
                cancelled=False,
                metrics={
                    "tool_duration_ms": duration_ms,
                },
                log_dir=self._log_dir,
            )

            await self._send_client(
                {
                    "type": "tool_result",
                    "response_id": pending.response_id,
                    "call_id": pending.call_id,
                    "duration_ms": duration_ms,
                    **result,
                }
            )

            if pending.name in DASHBOARD_TOOLS:
                views = get_views_for_frontend()

                if self._dashboard_logger:
                    self._dashboard_logger.info(
                        "VIEWS_UPDATE tool=%s call_id=%s views=%s",
                        pending.name,
                        pending.call_id,
                        len(views),
                    )

                await self._send_client(
                    {
                        "type": "views_update",
                        "views": views,
                    }
                )

            output = {
                "success": result.get("success", False),
                "tool": result.get("tool", pending.name),
                "payload": result.get("payload"),
                "error": result.get("error"),
                "warning": result.get("warning"),
                "dashboard_state": realtime_state(),
            }

            await self._send_qwen(
                {
                    "type": "conversation.item.create",
                    "item": {
                        "type": "function_call_output",
                        "call_id": pending.call_id,
                        "output": json.dumps(
                            output,
                            ensure_ascii=False,
                            separators=(",", ":"),
                            default=str,
                        ),
                    },
                }
            )

        # Ask Qwen for the natural-language/audio answer after every completed
        # tool batch.
        await self._send_qwen({"type": "response.create"})

    async def _handle_error(
        self,
        event: dict[str, Any],
    ) -> None:
        message = self._error_message(event)
        error = event.get("error")
        code = (
            error.get("code")
            if isinstance(error, dict)
            else None
        )

        # Keep compatibility with older frontends or in-flight upstream races.
        if code == "response_cancel_not_active":
            self._log_connection(
                "IGNORED_CANCEL_RACE %s",
                message,
            )
            return

        if self._event_logger:
            self._event_logger.error(
                "QWEN_ERROR %s",
                json.dumps(event, ensure_ascii=False),
            )

        await self._send_client(
            {
                "type": "error",
                "message": message,
                "code": code,
            }
        )

    # ------------------------------------------------------------------
    # Metrics and logging
    # ------------------------------------------------------------------

    def _response_metrics(
        self,
        response_id: str | None,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        metrics: dict[str, Any] = {}

        if response_id:
            created_at = self.response_created_at.pop(
                response_id,
                None,
            )
            first_audio_at = self.first_audio_at.pop(
                response_id,
                None,
            )

            if created_at and first_audio_at:
                metrics["response_created_to_first_audio_ms"] = round(
                    (first_audio_at - created_at) * 1000,
                    2,
                )

            if (
                self.last_user_speech_stopped_at
                and first_audio_at
            ):
                metrics["speech_stopped_to_first_audio_ms"] = round(
                    (
                        first_audio_at
                        - self.last_user_speech_stopped_at
                    )
                    * 1000,
                    2,
                )

        usage = response.get("usage")
        if isinstance(usage, dict):
            metrics["usage"] = usage

        return metrics

    def _init_session_loggers(self) -> None:
        if self._log_dir is not None:
            return

        log_dir, log_scope_id = resolve_session_log_dir(
            _LOG_ROOT,
            session_id=self.session_id,
            mode="qwen",
            analysis_id=self.analysis_id,
        )

        self._log_dir = log_dir
        self.log_scope_id = log_scope_id

        def make_logger(name: str) -> logging.Logger:
            logger = logging.getLogger(
                f"realtime_qwen.{name}."
                f"{self.session_id}.{self.log_scope_id}"
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

        # Keep the existing multi-file log layout.
        self._event_logger = make_logger("realtime_events")
        self._tool_logger = make_logger("tool_calls")
        self._dashboard_logger = make_logger("dashboard")
        self._bargein_logger = make_logger("bargein")
        self._connection_logger = make_logger("connection")
        self._conversation_logger = make_logger("conversation")

    def _log_event(self, event: dict[str, Any]) -> None:
        if self._event_logger:
            self._event_logger.info(
                "%s",
                json.dumps(
                    event,
                    ensure_ascii=False,
                    default=str,
                )[:10000],
            )

    def _log_connection(
        self,
        message: str,
        *args: Any,
    ) -> None:
        if self._connection_logger:
            self._connection_logger.info(message, *args)

    def _log_bargein(
        self,
        message: str,
        *args: Any,
    ) -> None:
        if self._bargein_logger:
            self._bargein_logger.info(message, *args)

    def _log_conversation(
        self,
        role: str,
        text: str,
    ) -> None:
        clean = str(text or "").strip()
        if not clean:
            return

        if self._conversation_logger:
            self._conversation_logger.info(
                "%s: %s",
                role,
                clean,
            )

        if self._log_dir:
            path = self._log_dir / "conversation.jsonl"
            with path.open("a", encoding="utf-8") as handle:
                handle.write(
                    json.dumps(
                        {
                            "ts": datetime.datetime.now(
                                datetime.timezone.utc
                            ).isoformat(),
                            "session_id": self.session_id,
                            "analysis_id": self.log_scope_id,
                            "role": role,
                            "text": clean,
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    # ------------------------------------------------------------------
    # Transport helpers
    # ------------------------------------------------------------------

    async def _send_qwen(
        self,
        message: dict[str, Any],
    ) -> bool:
        if self.qwen_ws is None:
            return False

        try:
            async with self._send_lock:
                await self.qwen_ws.send(
                    json.dumps(
                        message,
                        ensure_ascii=False,
                    )
                )
            return True
        except Exception as exc:
            self._log_connection(
                "SEND_QWEN_FAILED %s",
                exc,
            )
            return False

    async def _send_client(
        self,
        message: dict[str, Any],
    ) -> None:
        try:
            await self.client_ws.send_json(message)
        except Exception as exc:
            self._log_connection(
                "SEND_CLIENT_FAILED %s",
                exc,
            )

    async def _close_qwen(self) -> None:
        if self.qwen_ws is None:
            return

        with contextlib.suppress(Exception):
            await self.qwen_ws.close()

        self.qwen_ws = None
        self._log_connection("CLOSED")

    @staticmethod
    def _event_response_id(
        event: dict[str, Any],
    ) -> str | None:
        response = event.get("response")
        if isinstance(response, dict):
            response_id = response.get("id")
            if response_id:
                return str(response_id)

        response_id = event.get("response_id")
        return str(response_id) if response_id else None

    @staticmethod
    def _error_message(
        event: dict[str, Any],
    ) -> str:
        error = event.get("error")

        if isinstance(error, dict):
            return str(
                error.get("message")
                or error.get("code")
                or "Unknown Qwen error"
            )

        return str(error or "Unknown Qwen error")
