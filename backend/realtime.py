"""Qwen-Omni-Realtime runtime for VerbalVis FD-Voice.

This module is the only realtime implementation. It owns:

- the Qwen WebSocket session and Semantic VAD;
- immediate speech-start interruption (R-A);
- exactly one active assistant response;
- a non-preemptive, sequential dashboard-tool boundary with fail-fast dependencies;
- the browser event contract;
- events.jsonl and conversation.jsonl logs.

Tool execution is an input-closed window. Microphone chunks are blocked in the
browser, rejected again by the backend, and the Qwen input buffer is cleared
before tools run. Running tools are never cancelled or rolled back.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from dotenv import load_dotenv
from fastapi import WebSocket, WebSocketDisconnect
import websockets

from logging_utils import resolve_session_log_dir, safe_log_token
from prompts import build_system_prompt
from tool_contracts import batch_metadata, changes_dashboard, contract_for, result_summary
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

QWEN_API_KEY = (
    os.getenv("DASHSCOPE_API_KEY")
    or os.getenv("QWEN_API_KEY")
    or ""
).strip()
QWEN_MODEL = (
    os.getenv("QWEN_REALTIME_MODEL", "qwen3.5-omni-plus-realtime").strip()
    or "qwen3.5-omni-plus-realtime"
)
QWEN_VOICE = os.getenv("QWEN_VOICE", "Ethan").strip() or "Ethan"
QWEN_REGION = os.getenv("QWEN_REGION", "beijing").strip().lower()
QWEN_WORKSPACE_ID = os.getenv("QWEN_WORKSPACE_ID", "").strip()
QWEN_REALTIME_URL = os.getenv("QWEN_REALTIME_URL", "").strip()
QWEN_INPUT_SAMPLE_RATE = 16000
QWEN_OUTPUT_SAMPLE_RATE = 24000
QWEN_AUDIO_FORMAT = "pcm"
QWEN_TURN_DETECTION = "semantic_vad"
QWEN_VAD_THRESHOLD = float(os.getenv("QWEN_VAD_THRESHOLD", "0.4"))
QWEN_VAD_SILENCE_DURATION_MS = int(
    os.getenv("QWEN_VAD_SILENCE_DURATION_MS", "800")
)

LOG_ROOT = Path(__file__).parent / "logs"


@dataclass(frozen=True)
class PendingToolCall:
    call_id: str
    name: str
    arguments_raw: str
    response_id: str | None
    origin_user_transcript: str


def _with_model_query(url: str) -> str:
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["model"] = QWEN_MODEL
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            parts.path,
            urlencode(query),
            parts.fragment,
        )
    )


def _qwen_url() -> str:
    """Return the configured workspace endpoint or the DashScope fallback."""
    if QWEN_REALTIME_URL:
        return _with_model_query(QWEN_REALTIME_URL)

    if QWEN_WORKSPACE_ID:
        if QWEN_REGION in {"singapore", "ap-southeast-1", "intl"}:
            host = f"{QWEN_WORKSPACE_ID}.ap-southeast-1.maas.aliyuncs.com"
        else:
            host = f"{QWEN_WORKSPACE_ID}.cn-beijing.maas.aliyuncs.com"
        return f"wss://{host}/api-ws/v1/realtime?model={QWEN_MODEL}"

    host = (
        "dashscope-intl.aliyuncs.com"
        if QWEN_REGION in {"singapore", "ap-southeast-1", "intl"}
        else "dashscope.aliyuncs.com"
    )
    log.warning(
        "QWEN_WORKSPACE_ID is not configured; using the DashScope public realtime endpoint."
    )
    return f"wss://{host}/api-ws/v1/realtime?model={QWEN_MODEL}"


def _clean_schema(value: Any) -> Any:
    """Keep the conservative JSON-schema subset accepted by Qwen tools."""
    if isinstance(value, list):
        return [_clean_schema(item) for item in value if item is not None]
    if not isinstance(value, dict):
        return value

    cleaned: dict[str, Any] = {}
    for key, item in value.items():
        if key == "type" and isinstance(item, list):
            non_null = [entry for entry in item if entry != "null"]
            cleaned[key] = non_null[0] if len(non_null) == 1 else non_null
        elif key == "enum" and isinstance(item, list):
            enum_values = [entry for entry in item if entry is not None]
            if enum_values:
                cleaned[key] = enum_values
        else:
            cleaned[key] = _clean_schema(item)

    properties = cleaned.get("properties")
    if isinstance(properties, dict):
        for prop in properties.values():
            if not isinstance(prop, dict):
                continue
            if "type" not in prop and "enum" not in prop:
                prop["type"] = "string"
            if prop.get("type") == "array" and "items" not in prop:
                prop["items"] = {"type": "string"}
    return cleaned


def _qwen_tools() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    for schema in TOOL_SCHEMAS:
        nested = schema.get("function")
        function = nested if isinstance(nested, dict) else schema
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": function.get("name"),
                    "description": function.get("description", ""),
                    "parameters": _clean_schema(
                        function.get("parameters")
                        or {"type": "object", "properties": {}}
                    ),
                },
            }
        )
    return tools


class QwenRealtimeSession:
    """One browser WebSocket connected to one Qwen Realtime session."""

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
        self.log_scope_id = self.analysis_id or safe_log_token(session_id, "session")
        self.model = model or QWEN_MODEL

        self.qwen_ws: Any = None
        self.running = False
        self.tool_running = False
        self.ignored_audio_chunks = 0

        self.current_response_id: str | None = None
        self.playback_response_id: str | None = None
        self.interrupted_response_ids: set[str] = set()
        self.cancel_requested_response_ids: set[str] = set()
        self.last_user_transcript = ""
        self.assistant_transcript = ""

        self.last_speech_stopped_at: float | None = None
        self.response_created_at: dict[str, float] = {}
        self.first_audio_at: dict[str, float] = {}
        self.playback_stop_started_at: dict[str, float] = {}

        self._send_lock = asyncio.Lock()
        self._log_dir: Path | None = None

    async def start(self) -> None:
        init_views()
        self._init_logs()
        self.running = True

        if not await self._send_client(
            {
                "type": "init",
                "views": get_views_for_frontend(),
                **self._session_metadata(),
            }
        ):
            return

        try:
            await self._connect_qwen()
            if not await self._configure_qwen():
                return

            client_task = asyncio.create_task(self._client_to_qwen())
            qwen_task = asyncio.create_task(self._qwen_to_client())
            done, pending = await asyncio.wait(
                {client_task, qwen_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            error: BaseException | None = None
            for task in done:
                if not task.cancelled() and task.exception() and error is None:
                    error = task.exception()
            for task in pending:
                task.cancel()
            for task in pending:
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            if error:
                raise error
        except WebSocketDisconnect:
            self._event("client_disconnected")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._event("session_error", error=str(exc))
            await self._send_client({"type": "error", "message": str(exc)})
            raise
        finally:
            self.running = False
            await self._close_qwen()

    async def _connect_qwen(self) -> None:
        if not QWEN_API_KEY:
            raise RuntimeError("DASHSCOPE_API_KEY or QWEN_API_KEY is not configured")

        url = _qwen_url()
        self._event("qwen_connecting", model=self.model, url=url)
        self.qwen_ws = await websockets.connect(
            url,
            additional_headers={
                "Authorization": f"Bearer {QWEN_API_KEY}",
                "X-DashScope-DataInspection": "enable",
            },
            max_size=2**24,
            ping_interval=20,
            ping_timeout=20,
        )
        self._event("qwen_connected")

    async def _configure_qwen(self) -> bool:
        await self._send_qwen(
            {
                "type": "session.update",
                "session": {
                    "modalities": ["text", "audio"],
                    "instructions": self._instructions(),
                    "voice": QWEN_VOICE,
                    "input_audio_format": QWEN_AUDIO_FORMAT,
                    "output_audio_format": QWEN_AUDIO_FORMAT,
                    "input_audio_transcription": {
                        "model": "qwen3-asr-flash-realtime",
                    },
                    "turn_detection": {
                        "type": QWEN_TURN_DETECTION,
                        "threshold": QWEN_VAD_THRESHOLD,
                        "silence_duration_ms": QWEN_VAD_SILENCE_DURATION_MS,
                    },
                    "tools": _qwen_tools(),
                },
            }
        )

        while self.running:
            raw = await asyncio.wait_for(self.qwen_ws.recv(), timeout=20)
            event = json.loads(raw)
            self._log_qwen_event(event)
            if event.get("type") == "session.updated":
                await self._send_client(
                    {"type": "session_updated", **self._session_metadata()}
                )
                await self._send_client(
                    {"type": "dashboard_state", "state": realtime_state()}
                )
                await self._send_runtime("ready")
                return await self._send_client({"type": "session_ready"})
            if event.get("type") == "error":
                raise RuntimeError(self._error_message(event))
        return False

    def _instructions(self) -> str:
        state = json.dumps(
            realtime_state(),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return f"{build_system_prompt()}\n\nCURRENT DASHBOARD METADATA:\n{state}"

    def _session_metadata(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "analysis_id": self.log_scope_id,
            "mode": "barge_in",
            "condition_code": "fd_voice",
            "input_mode": "semantic_vad",
            "turn_detection": QWEN_TURN_DETECTION,
            "provider": "qwen",
            "model": self.model,
            "voice": QWEN_VOICE,
            "input_audio_rate": QWEN_INPUT_SAMPLE_RATE,
            "output_audio_rate": QWEN_OUTPUT_SAMPLE_RATE,
            "audio_format": QWEN_AUDIO_FORMAT,
        }

    async def _client_to_qwen(self) -> None:
        while self.running:
            try:
                raw = await self.client_ws.receive_text()
            except WebSocketDisconnect:
                self.running = False
                return
            except RuntimeError as exc:
                if self._is_disconnect_error(exc):
                    self.running = False
                    return
                raise

            message = json.loads(raw)
            message_type = message.get("type")
            if message_type == "audio":
                if self.tool_running:
                    self.ignored_audio_chunks += 1
                    continue
                audio = message.get("data")
                if audio:
                    await self._send_qwen(
                        {"type": "input_audio_buffer.append", "audio": audio}
                    )
            elif message_type == "playback_stopped":
                self._handle_playback_stopped(message)
            elif message_type in {"close", "disconnect"}:
                self.running = False
                return

    async def _qwen_to_client(self) -> None:
        async for raw in self.qwen_ws:
            event = json.loads(raw)
            self._log_qwen_event(event)
            event_type = event.get("type", "")

            if event_type in {"session.created", "session.updated"}:
                continue
            if event_type == "response.created":
                await self._response_created(event)
            elif event_type == "response.audio.delta":
                await self._audio_delta(event)
            elif event_type == "response.audio_transcript.delta":
                await self._assistant_transcript_delta(event)
            elif event_type == "response.audio_transcript.done":
                await self._assistant_transcript_done(event)
            elif event_type == "input_audio_buffer.speech_started":
                await self._speech_started(event)
            elif event_type == "input_audio_buffer.speech_stopped":
                await self._speech_stopped(event)
            elif event_type == "conversation.item.input_audio_transcription.delta":
                await self._user_transcript_delta(event)
            elif event_type == "conversation.item.input_audio_transcription.completed":
                await self._user_transcript_completed(event)
            elif event_type == "response.done":
                await self._response_done(event)
            elif event_type == "error":
                await self._handle_error(event)

    async def _response_created(self, event: dict[str, Any]) -> None:
        response = event.get("response")
        response_id = (
            response.get("id")
            if isinstance(response, dict)
            else event.get("response_id")
        )
        if not response_id:
            return
        response_id = str(response_id)

        if self.current_response_id and self.current_response_id != response_id:
            old_id = self.current_response_id
            self.interrupted_response_ids.add(old_id)
            await self._send_client(
                {
                    "type": "assistant_playback_stop",
                    "response_id": old_id,
                    "reason": "superseded_by_new_response",
                    "clear_queue": True,
                }
            )

        self.current_response_id = response_id
        self.assistant_transcript = ""
        self.response_created_at[response_id] = time.perf_counter()
        self._event("assistant_response_started", response_id=response_id)
        await self._send_client(
            {"type": "assistant_response_started", "response_id": response_id}
        )

    async def _audio_delta(self, event: dict[str, Any]) -> None:
        response_id = self._event_response_id(event)
        if not response_id or response_id != self.current_response_id:
            return
        if response_id not in self.first_audio_at:
            self.first_audio_at[response_id] = time.perf_counter()

        if await self._send_client(
            {
                "type": "audio",
                "data": event.get("delta", ""),
                "response_id": response_id,
                "item_id": event.get("item_id"),
                "content_index": event.get("content_index", 0),
                "sample_rate": QWEN_OUTPUT_SAMPLE_RATE,
            }
        ):
            self.playback_response_id = response_id

    async def _assistant_transcript_delta(self, event: dict[str, Any]) -> None:
        response_id = self._event_response_id(event)
        if not response_id or response_id != self.current_response_id:
            return
        delta = str(event.get("delta") or "")
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

    async def _assistant_transcript_done(self, event: dict[str, Any]) -> None:
        response_id = self._event_response_id(event)
        if not response_id or response_id != self.current_response_id:
            return
        transcript = str(event.get("transcript") or "").strip()
        if transcript:
            self.assistant_transcript = transcript

    async def _speech_started(self, event: dict[str, Any]) -> None:
        if self.tool_running:
            self._event("speech_ignored_during_tool")
            return

        utterance_id = event.get("item_id") or event.get("utterance_id")
        await self._send_client(
            {"type": "speech_started", "utterance_id": utterance_id}
        )

        active_id = self.current_response_id
        response_id = active_id or self.playback_response_id
        if not response_id:
            return

        self.playback_stop_started_at[response_id] = time.perf_counter()
        self._event("barge_in", response_id=response_id, utterance_id=utterance_id)
        if active_id:
            self.interrupted_response_ids.add(active_id)
            self.cancel_requested_response_ids.add(active_id)
            self.current_response_id = None
            self.assistant_transcript = ""

        await self._send_client(
            {
                "type": "assistant_playback_stop",
                "response_id": response_id,
                "reason": "semantic_vad_speech_started",
                "clear_queue": True,
            }
        )
        if active_id:
            await self._send_qwen({"type": "response.cancel"})

    async def _speech_stopped(self, event: dict[str, Any]) -> None:
        if self.tool_running:
            return
        self.last_speech_stopped_at = time.perf_counter()
        await self._send_client(
            {
                "type": "speech_stopped",
                "utterance_id": event.get("item_id") or event.get("utterance_id"),
            }
        )

    async def _user_transcript_delta(self, event: dict[str, Any]) -> None:
        if self.tool_running:
            return
        preview = (
            str(event.get("text") or "") + str(event.get("stash") or "")
        ).strip()
        if preview:
            await self._send_client(
                {
                    "type": "transcript",
                    "role": "user",
                    "text": preview,
                    "status": "partial",
                    "completed": False,
                    "utterance_id": event.get("item_id"),
                }
            )

    async def _user_transcript_completed(self, event: dict[str, Any]) -> None:
        if self.tool_running:
            self._event("user_transcript_ignored_during_tool")
            return
        transcript = str(event.get("transcript") or "").strip()
        if not transcript:
            return
        self.last_user_transcript = transcript
        self._conversation("YOU", transcript)
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

    async def _response_done(self, event: dict[str, Any]) -> None:
        response = event.get("response")
        response = response if isinstance(response, dict) else {}
        response_id = str(response.get("id") or "") or None
        status = str(response.get("status") or "")

        if response_id:
            self.cancel_requested_response_ids.discard(response_id)
        if response_id in self.interrupted_response_ids:
            self.interrupted_response_ids.discard(response_id)
            self._response_metrics(response_id, response)
            self._event(
                "response_discarded",
                response_id=response_id,
                reason="user_interruption",
            )
            return
        if not response_id:
            return
        if response_id != self.current_response_id:
            self._response_metrics(response_id, response)
            self._event(
                "response_discarded",
                response_id=response_id,
                reason="not_current",
            )
            return

        self.current_response_id = None
        metrics = self._response_metrics(response_id, response)
        if status != "completed":
            self.assistant_transcript = ""
            await self._send_client(
                {
                    "type": "response_done",
                    "response_id": response_id,
                    "status": status,
                    "metrics": metrics,
                }
            )
            return

        tool_calls = self._tool_calls_from_response(response)
        if tool_calls:
            # Close the tool-selection response in the browser before the
            # separate post-tool response starts. Empty assistant rows are
            # removed by the frontend store.
            await self._send_client(
                {
                    "type": "response_done",
                    "response_id": response_id,
                    "status": "tool_call",
                    "metrics": metrics,
                }
            )
            self.assistant_transcript = ""
            await self._execute_tool_batch(tool_calls)
            return

        transcript = (
            self.assistant_transcript.strip()
            or self._transcript_from_response(response)
        )
        if transcript:
            self._conversation("AI", transcript)
        self.assistant_transcript = ""
        await self._send_client(
            {
                "type": "response_done",
                "response_id": response_id,
                "status": status,
                "metrics": metrics,
            }
        )

    def _tool_calls_from_response(
        self,
        response: dict[str, Any],
    ) -> list[PendingToolCall]:
        response_id = str(response.get("id") or "") or None
        calls: list[PendingToolCall] = []
        seen: set[str] = set()
        for item in response.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            if item.get("status") not in {None, "completed"}:
                continue
            call_id = str(item.get("call_id") or "")
            name = str(item.get("name") or "")
            if not call_id or not name or call_id in seen:
                continue
            seen.add(call_id)
            arguments = item.get("arguments") or "{}"
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments, ensure_ascii=False)
            calls.append(
                PendingToolCall(
                    call_id=call_id,
                    name=name,
                    arguments_raw=arguments,
                    response_id=response_id,
                    origin_user_transcript=self.last_user_transcript,
                )
            )
        return calls

    async def _execute_tool_batch(self, calls: list[PendingToolCall]) -> None:
        if not calls:
            return

        response_id = calls[0].response_id
        started_at = time.perf_counter()
        metadata = batch_metadata(call.name for call in calls)
        dashboard_change = any(changes_dashboard(call.name) for call in calls)
        completed = 0
        successful = 0
        skipped = 0
        followup_requested = False

        self.tool_running = True
        self.ignored_audio_chunks = 0
        # Remove any partial audio that reached Qwen immediately before the
        # browser received the tool-running state.
        await self._send_qwen({"type": "input_audio_buffer.clear"})
        await self._send_client(
            {
                "type": "tool_execution_started",
                "response_id": response_id,
                "tool_count": len(calls),
                "tools": metadata,
                "changes_dashboard": dashboard_change,
            }
        )
        await self._send_runtime(
            "updating_dashboard" if dashboard_change else "reading_dashboard",
            tools=metadata,
        )
        self._event("tool_batch_started", response_id=response_id, tools=metadata)

        try:
            blocking_failure: str | None = None
            for pending in calls:
                result = await self._execute_one_tool(
                    pending,
                    skip_reason=blocking_failure,
                )
                completed += 1
                if result.get("success"):
                    successful += 1
                elif blocking_failure is not None:
                    skipped += 1
                else:
                    blocking_failure = (
                        f"Skipped because the earlier tool {pending.name} failed"
                    )
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            ignored = self.ignored_audio_chunks
            self.tool_running = False
            self.ignored_audio_chunks = 0

            if self.running:
                # Official Qwen tool flow: all function_call_output items first,
                # then one response.create for the final spoken answer.
                followup_requested = await self._send_qwen(
                    {"type": "response.create"}
                )

            await self._send_client(
                {
                    "type": "tool_execution_finished",
                    "response_id": response_id,
                    "tool_count": len(calls),
                    "completed_count": completed,
                    "successful_count": successful,
                    "failed_count": max(0, completed - successful),
                    "skipped_count": skipped,
                    "duration_ms": duration_ms,
                    "ignored_audio_chunks": ignored,
                    "followup_requested": followup_requested,
                    "changes_dashboard": dashboard_change,
                    "tools": metadata,
                }
            )
            await self._send_client(
                {"type": "dashboard_state", "state": realtime_state()}
            )
            await self._send_runtime(
                "processing" if followup_requested else "ready"
            )
            self._event(
                "tool_batch_finished",
                response_id=response_id,
                completed=completed,
                successful=successful,
                skipped=skipped,
                duration_ms=duration_ms,
                ignored_audio_chunks=ignored,
            )

    async def _execute_one_tool(
        self,
        pending: PendingToolCall,
        *,
        skip_reason: str | None = None,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()
        argument_error: str | None = None
        try:
            raw_arguments = json.loads(pending.arguments_raw or "{}")
            if not isinstance(raw_arguments, dict):
                argument_error = "Tool arguments must decode to a JSON object"
                raw_arguments = {}
        except json.JSONDecodeError as exc:
            argument_error = f"Invalid JSON tool arguments: {exc.msg}"
            raw_arguments = {}

        arguments = normalize_tool_arguments(
            pending.name,
            raw_arguments,
            user_transcript=pending.origin_user_transcript,
        )
        await self._send_client(
            {
                "type": "tool_call",
                "name": pending.name,
                "arguments": json.dumps(arguments, ensure_ascii=False),
                "response_id": pending.response_id,
                "call_id": pending.call_id,
                "contract": contract_for(pending.name),
            }
        )

        if skip_reason:
            result = {
                "tool": pending.name,
                "success": False,
                "payload": None,
                "error": skip_reason,
            }
        elif argument_error:
            result = {
                "tool": pending.name,
                "success": False,
                "payload": None,
                "error": argument_error,
            }
        else:
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
                    "tool": pending.name,
                    "success": False,
                    "payload": None,
                    "error": str(exc),
                }

        duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
        summary = result_summary(pending.name, result)
        log_tool_call(
            session_id=self.session_id,
            analysis_id=self.log_scope_id,
            tool_name=pending.name,
            params=arguments,
            response_id=pending.response_id,
            call_id=pending.call_id,
            result_success=result.get("success"),
            metrics={"tool_duration_ms": duration_ms},
            log_dir=self._log_dir,
        )
        self._event(
            "tool_result",
            response_id=pending.response_id,
            call_id=pending.call_id,
            tool=pending.name,
            parameters=arguments,
            success=result.get("success"),
            duration_ms=duration_ms,
        )
        await self._send_client(
            {
                "type": "tool_result",
                "response_id": pending.response_id,
                "call_id": pending.call_id,
                "duration_ms": duration_ms,
                "summary": summary,
                **result,
            }
        )

        if changes_dashboard(pending.name) and result.get("success"):
            await self._send_client(
                {"type": "views_update", "views": get_views_for_frontend()}
            )
            await self._send_client(
                {"type": "dashboard_state", "state": realtime_state()}
            )

        output = {
            "success": result.get("success", False),
            "tool": result.get("tool", pending.name),
            "payload": result.get("payload"),
            "error": result.get("error"),
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
        return result

    async def _handle_error(self, event: dict[str, Any]) -> None:
        if self._is_cancel_race(event):
            self.cancel_requested_response_ids.clear()
            self._event("cancel_race_ignored", payload=event)
            return
        message = self._error_message(event)
        self._event("qwen_error", error=message, payload=event)
        await self._send_client({"type": "error", "message": message})

    async def _send_runtime(
        self,
        phase: str,
        *,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        await self._send_client(
            {
                "type": "runtime_state",
                "phase": phase,
                "tool_running": self.tool_running,
                "tools": tools or [],
            }
        )

    async def _send_qwen(self, payload: dict[str, Any]) -> bool:
        if not self.qwen_ws or not self.running:
            return False
        try:
            async with self._send_lock:
                await self.qwen_ws.send(json.dumps(payload, ensure_ascii=False))
            return True
        except Exception as exc:
            self._event(
                "qwen_send_error",
                error=str(exc),
                payload_type=payload.get("type"),
            )
            return False

    async def _send_client(self, payload: dict[str, Any]) -> bool:
        try:
            await self.client_ws.send_json(payload)
            return True
        except (WebSocketDisconnect, RuntimeError):
            self.running = False
            return False

    async def _close_qwen(self) -> None:
        if not self.qwen_ws:
            return
        with contextlib.suppress(Exception):
            await self.qwen_ws.close()
        self.qwen_ws = None

    def _response_metrics(
        self,
        response_id: str | None,
        response: dict[str, Any],
    ) -> dict[str, Any]:
        metrics: dict[str, Any] = {}
        if response_id:
            created = self.response_created_at.pop(response_id, None)
            first_audio = self.first_audio_at.pop(response_id, None)
            if created and first_audio:
                metrics["response_created_to_first_audio_ms"] = round(
                    (first_audio - created) * 1000,
                    2,
                )
            if self.last_speech_stopped_at and first_audio:
                metrics["speech_stopped_to_first_audio_ms"] = round(
                    (first_audio - self.last_speech_stopped_at) * 1000,
                    2,
                )
        usage = response.get("usage")
        if isinstance(usage, dict):
            metrics["usage"] = usage
        return metrics

    def _handle_playback_stopped(self, message: dict[str, Any]) -> None:
        response_id = str(message.get("response_id") or "") or None
        started = (
            self.playback_stop_started_at.pop(response_id, None)
            if response_id
            else None
        )
        latency_ms = (
            round((time.perf_counter() - started) * 1000, 2)
            if started
            else None
        )
        self._event(
            "playback_stopped",
            response_id=response_id,
            reason=message.get("reason"),
            playback_cursor=message.get("playback_cursor"),
            latency_ms=latency_ms,
        )
        if not response_id or self.playback_response_id == response_id:
            self.playback_response_id = None

    def _init_logs(self) -> None:
        directory, scope = resolve_session_log_dir(
            LOG_ROOT,
            session_id=self.session_id,
            mode="audio",
            analysis_id=self.analysis_id,
        )
        self._log_dir = directory
        self.log_scope_id = scope
        self._event("session_started", **self._session_metadata())

    def _event(self, event: str, **payload: Any) -> None:
        if not self._log_dir:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "session_id": self.session_id,
            "analysis_id": self.log_scope_id,
            "condition_code": "fd_voice",
            **payload,
        }
        with (self._log_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def _conversation(self, role: str, text: str) -> None:
        clean = " ".join(str(text or "").split())
        if not clean or not self._log_dir:
            return
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "session_id": self.session_id,
            "analysis_id": self.log_scope_id,
            "role": role,
            "text": clean,
        }
        with (self._log_dir / "conversation.jsonl").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _log_qwen_event(self, event: dict[str, Any]) -> None:
        self._event(
            "qwen_event",
            qwen_type=event.get("type"),
            payload=self._compact_qwen_event(event),
        )

    @staticmethod
    def _compact_qwen_event(event: dict[str, Any]) -> dict[str, Any]:
        compact = dict(event)
        if event.get("type") == "response.audio.delta":
            delta = str(compact.pop("delta", ""))
            compact["audio_base64_chars"] = len(delta)
        return compact

    @staticmethod
    def _transcript_from_response(response: dict[str, Any]) -> str:
        parts: list[str] = []
        for item in response.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "message":
                continue
            for content in item.get("content") or []:
                if not isinstance(content, dict):
                    continue
                text = content.get("transcript") or content.get("text") or ""
                if text:
                    parts.append(str(text))
        return "".join(parts).strip()

    @staticmethod
    def _event_response_id(event: dict[str, Any]) -> str | None:
        response_id = event.get("response_id")
        if response_id:
            return str(response_id)
        response = event.get("response")
        if isinstance(response, dict) and response.get("id"):
            return str(response["id"])
        return None

    def _is_cancel_race(self, event: dict[str, Any]) -> bool:
        if not self.cancel_requested_response_ids:
            return False
        error = event.get("error") if isinstance(event.get("error"), dict) else {}
        combined = " ".join(
            str(error.get(key) or "").lower()
            for key in ("code", "message", "param")
        )
        return (
            "cancel" in combined
            and any(
                phrase in combined
                for phrase in (
                    "not active",
                    "no active",
                    "cannot cancel",
                    "already completed",
                )
            )
        )

    @staticmethod
    def _error_message(event: dict[str, Any]) -> str:
        error = event.get("error")
        if isinstance(error, dict):
            return str(error.get("message") or error.get("code") or error)
        return str(error or event.get("message") or "Qwen realtime error")

    @staticmethod
    def _is_disconnect_error(exc: RuntimeError) -> bool:
        text = str(exc).lower()
        return "disconnect" in text or "websocket is not connected" in text
