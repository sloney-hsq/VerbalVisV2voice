"""
VerbalVis Realtime API manager.
Bridges the frontend WebSocket and the OpenAI Realtime WebSocket.
"""

from __future__ import annotations

import asyncio
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
from fastapi import WebSocket

from prompts import build_system_prompt
from tools import (
    TOOL_SCHEMAS,
    context_text,
    execute_tool,
    get_views_for_frontend,
    init_views,
    log_tool_call,
)

load_dotenv()
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Structured event logging — per-session timestamped directory under logs/
# Borrowed from realtime copy.py (verified working). Terminal stays clean;
# verbose Realtime events go to files only.
# ---------------------------------------------------------------------------
_LOG_ROOT = Path(__file__).parent / "logs"
_LOG_ROOT.mkdir(exist_ok=True)
_LOG_FMT = logging.Formatter("%(asctime)s.%(msecs)03d  %(message)s", datefmt="%H:%M:%S")

# Events worth printing to terminal. Everything else goes to file only.
IMPORTANT_EVENTS = {
    "session.updated",
    "input_audio_buffer.speech_started",
    "input_audio_buffer.speech_stopped",
    "conversation.item.input_audio_transcription.completed",
    "response.created",
    "response.function_call_arguments.done",
    "response.output_audio_transcript.done",
    "response.done",
    "error",
}

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
REALTIME_MODEL = os.getenv("OPENAI_REALTIME_MODEL", "gpt-realtime-2")
REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"
REALTIME_VOICE = os.getenv("OPENAI_REALTIME_VOICE", "alloy")
TRANSCRIPTION_MODEL = os.getenv("OPENAI_REALTIME_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe")
REASONING_EFFORT = os.getenv("OPENAI_REALTIME_REASONING_EFFORT", "low")
OPENAI_RECONNECT_ATTEMPTS = int(os.getenv("OPENAI_REALTIME_RECONNECT_ATTEMPTS", "2"))

# Set to False for turn-based baseline (user study control condition).
# Keep False until ASR/TTS/Tool fully verified end-to-end on GA.
BARGE_IN_ENABLED = False


class RealtimeSession:
    """One session = one frontend client + one OpenAI Realtime connection."""

    def __init__(self, client_ws: WebSocket, session_id: str = "default"):
        self.client_ws = client_ws
        self.session_id = session_id
        self.openai_ws: Any = None
        self.current_response_id: str | None = None

        self._running = False
        self._openai_send_lock = asyncio.Lock()
        self._tool_state_lock = asyncio.Lock()
        self._tool_tasks: set[asyncio.Task] = set()
        self._invalidated_response_ids: set[str] = set()
        self._turn_epoch = 0

        # Coordinates response.create across multiple function calls that
        # belong to the same model turn (the Realtime API can emit several
        # tool calls in one response). Keyed by response_id.
        self._pending_tool_calls: dict[str, int] = {}
        self._pending_should_respond: dict[str, bool] = {}

        self._session_update_profiles = ("primary", "no_reasoning", "no_transcription", "minimal")
        self._session_update_profile_index = 0
        self._session_update_pending = False
        self._session_updated = asyncio.Event()
        # Single-phase backend already configures OpenAI on connect, so any
        # client `start_session` is just a handshake ping. Dedup it so repeated
        # button presses on the frontend don't spam the relay.
        self._session_started = False

        self._last_user_speech_stopped_at: float | None = None
        self._last_manual_commit_at: float | None = None
        self._response_metrics: dict[str, dict[str, Any]] = {}
        self._timeline: list[dict[str, Any]] = []

        # Per-session loggers (initialised in start()).
        self._log_dir: Path | None = None
        self._event_logger: logging.Logger | None = None
        self._tool_logger: logging.Logger | None = None
        self._dashboard_logger: logging.Logger | None = None
        self._bargein_logger: logging.Logger | None = None

    # ------------------------------------------------------------------
    # Per-session logging setup
    # ------------------------------------------------------------------

    def _init_session_loggers(self) -> None:
        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self._log_dir = _LOG_ROOT / f"{ts}_{self.session_id}"
        self._log_dir.mkdir(parents=True, exist_ok=True)

        def _make(name: str) -> logging.Logger:
            logger = logging.getLogger(f"realtime.{name}.{self.session_id}.{ts}")
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
            logger.handlers.clear()
            fh = logging.FileHandler(self._log_dir / f"{name}.log", encoding="utf-8")
            fh.setFormatter(_LOG_FMT)
            logger.addHandler(fh)
            return logger

        self._event_logger = _make("realtime_events")
        self._tool_logger = _make("tool_calls")
        self._dashboard_logger = _make("dashboard")
        self._bargein_logger = _make("bargein")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Connect to OpenAI and start bidirectional relay (single-phase)."""
        self._init_session_loggers()
        init_views()
        self._running = True

        await self._send_client({
            "type": "init",
            "views": get_views_for_frontend(),
            "mode": "barge_in" if BARGE_IN_ENABLED else "turn_based",
        })

        try:
            await self._connect_and_configure_openai()
            await self._inject_context("Session started. Dashboard shows 4 base views with full dataset.")

            client_task = asyncio.create_task(self._client_to_openai(), name=f"{self.session_id}:client_to_openai")
            openai_task = asyncio.create_task(self._openai_loop(), name=f"{self.session_id}:openai_loop")
            done, pending = await asyncio.wait(
                {client_task, openai_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                if task.cancelled():
                    continue
                exc = task.exception()
                if exc:
                    log.info("Session task ended with error: %s", exc)

            self._running = False
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
        except Exception as exc:
            log.info("Session ended: %s", exc)
            await self._send_client({
                "type": "error",
                "message": str(exc),
            })
        finally:
            self._running = False
            await self._shutdown()

    async def _connect_and_configure_openai(self) -> None:
        if not OPENAI_API_KEY:
            raise RuntimeError("OPENAI_API_KEY is not set.")

        log.warning("=== CONNECTING OPENAI ===")
        headers = {"Authorization": f"Bearer {OPENAI_API_KEY}"}
        self.openai_ws = await websockets.connect(
            REALTIME_URL,
            additional_headers=headers,
            max_size=2**24,
            ping_interval=20,
            ping_timeout=20,
        )
        log.warning("=== OPENAI CONNECTED ===")
        self._record_timeline("openai.connected")
        profile = self._session_update_profiles[self._session_update_profile_index]
        log.warning("=== SENDING SESSION UPDATE ===")
        await self._send_session_update(profile=profile)
        # Block until OpenAI confirms session.updated (or returns an error).
        # Without this, conversation.item.create / audio.append / response.create
        # race the still-pending session configuration.
        await self._wait_for_session_updated()
        log.warning("=== SESSION UPDATED ===")
        # Single-phase: configuration is done as soon as we connect, so notify
        # the frontend now rather than waiting for it to send `start_session`.
        # The frontend gates mic on `session_ready`, so without this it polls
        # for 15s and re-sends `start_session` on every button press.
        self._session_started = True
        await self._send_client({"type": "session_ready"})

    async def _openai_loop(self) -> None:
        reconnects = 0
        while self._running:
            try:
                await self._openai_to_client()
                if not self._running:
                    break
                raise RuntimeError("OpenAI Realtime connection closed.")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                if not self._running:
                    break
                reconnects += 1
                log.warning("OpenAI relay stopped (%s/%s): %s", reconnects, OPENAI_RECONNECT_ATTEMPTS, exc)
                if reconnects > OPENAI_RECONNECT_ATTEMPTS:
                    await self._send_client({
                        "type": "error",
                        "message": "OpenAI Realtime connection closed and reconnect attempts were exhausted.",
                    })
                    self._running = False
                    break

                await self._send_client({
                    "type": "reconnecting",
                    "attempt": reconnects,
                })
                await self._close_openai()
                await asyncio.sleep(min(2 ** reconnects, 8))
                await self._connect_and_configure_openai()
                await self._inject_context(context_text())

    async def _shutdown(self) -> None:
        for task in list(self._tool_tasks):
            task.cancel()
        if self._tool_tasks:
            await asyncio.gather(*self._tool_tasks, return_exceptions=True)
        await self._close_openai()

    async def _close_openai(self) -> None:
        if self.openai_ws:
            with contextlib.suppress(Exception):
                await self.openai_ws.close()
        self.openai_ws = None

    # ------------------------------------------------------------------
    # Session configuration (GA gpt-realtime-2 schema)
    # ------------------------------------------------------------------

    async def _send_session_update(self, profile: str) -> None:
        self._session_update_pending = True
        self._session_updated.clear()
        self._record_timeline("session.update.sent", profile=profile)

        payload = {
            "type": "session.update",
            "session": self._build_session_config(profile),
        }

        if self._event_logger:
            self._event_logger.info("SESSION_UPDATE_SENT %s", json.dumps(payload, ensure_ascii=False))
        print("\n================ SESSION UPDATE ================")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        print("================================================\n")

        await self._send_openai(payload)

    def _build_session_config(self, profile: str) -> dict[str, Any]:
        # GA gpt-realtime-2 schema:
        #   - audio.input.format   MUST be object {"type":"audio/pcm","rate":24000}.
        #     The short string "pcm16" is rejected by GA with
        #     'Invalid type for session.audio.input.format: expected an object'.
        #   - audio.input.turn_detection
        #   - audio.input.transcription
        #   - audio.output.format  (same object form as input)
        #   - audio.output.voice
        #   - reasoning lives at session root.
        audio_input: dict[str, Any] = {
            "format": {
                "type": "audio/pcm",
                "rate": 24000,
            },
        }

        if profile != "minimal" and BARGE_IN_ENABLED:
            audio_input["turn_detection"] = {
                "type": "semantic_vad",
                "eagerness": "low",
                "create_response": True,
                # The actual barge-in switch — server auto-cancels in-progress
                # response when speech_started fires.
                "interrupt_response": True,
            }

        if profile in {"primary", "no_reasoning"}:
            audio_input["transcription"] = {"model": TRANSCRIPTION_MODEL}

        session: dict[str, Any] = {
            "type": "realtime",
            "instructions": build_system_prompt(),
            "tools": TOOL_SCHEMAS,
            "tool_choice": "auto",
            "audio": {
                "input": audio_input,
                "output": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": 24000,
                    },
                    "voice": REALTIME_VOICE,
                },
            },
        }

        if profile in {"primary", "no_transcription"}:
            session["reasoning"] = {"effort": REASONING_EFFORT}

        return session

    async def _retry_session_update_after_schema_error(self, error: dict[str, Any]) -> bool:
        # ── SHORT-CIRCUITED: surface schema errors instead of auto-downgrading. ──
        return False

    async def _wait_for_session_updated(self) -> None:
        """Read startup events until session.update is accepted or clearly rejected."""
        while self._session_update_pending and self._running:
            raw = await asyncio.wait_for(self.openai_ws.recv(), timeout=15)
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
                    "model": REALTIME_MODEL,
                    "profile": self._session_update_profiles[self._session_update_profile_index],
                    "mode": "barge_in" if BARGE_IN_ENABLED else "turn_based",
                })
                return

            if etype == "error":
                error = event.get("error", {})
                if await self._retry_session_update_after_schema_error(error):
                    continue
                raise RuntimeError(str(error.get("message", "session.update failed")))

    # ------------------------------------------------------------------
    # Client -> OpenAI relay
    # ------------------------------------------------------------------

    async def _client_to_openai(self) -> None:
        """Forward audio / control messages from frontend to OpenAI."""
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
                    await self._send_openai({
                        "type": "input_audio_buffer.append",
                        "audio": msg["data"],
                    })
                elif msg_type == "commit":
                    self._last_manual_commit_at = time.perf_counter()
                    self._record_timeline("client.commit")
                    await self._send_openai({"type": "input_audio_buffer.commit"})
                    await self._send_openai({"type": "response.create"})
                elif msg_type == "start_session":
                    # Single-phase backend already configured OpenAI in start();
                    # dedup repeated handshakes (frontend polls sessionReady and
                    # re-sends on every Start Mic click). Just re-ack so the
                    # frontend's sessionReady flips.
                    if self._session_started:
                        log.warning("duplicate start_session ignored")
                        if self._event_logger:
                            self._event_logger.info("CLIENT start_session DEDUP")
                        await self._send_client({"type": "session_ready"})
                        continue
                    self._session_started = True
                    await self._send_client({"type": "session_ready"})
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.info("Client relay stopped: %s", exc)
            self._running = False

    # ------------------------------------------------------------------
    # OpenAI -> Client relay
    # ------------------------------------------------------------------

    async def _openai_to_client(self) -> None:
        """Process events from OpenAI and relay to frontend."""
        async for raw in self.openai_ws:
            event = json.loads(raw)
            etype = event.get("type", "")

            # File: every event. Terminal: only the high-signal ones.
            if self._event_logger:
                self._event_logger.info("%s", raw[:2000] if len(raw) > 2000 else raw)
            if etype in IMPORTANT_EVENTS:
                print(f"\n[{etype}] {raw[:1000]}\n")

            response_id = self._event_response_id(event)
            self._record_timeline(etype, response_id=response_id)

            if etype == "session.updated":
                self._session_update_pending = False
                self._session_updated.set()
                await self._send_client({
                    "type": "session_updated",
                    "model": REALTIME_MODEL,
                    "profile": self._session_update_profiles[self._session_update_profile_index],
                    "mode": "barge_in" if BARGE_IN_ENABLED else "turn_based",
                })

            elif etype == "response.created":
                resp = event.get("response", {})
                self.current_response_id = resp.get("id")
                self._start_response_metrics(self.current_response_id)

            # GA renamed response.audio.delta → response.output_audio.delta.
            # Accept both for safety.
            elif etype in ("response.audio.delta", "response.output_audio.delta"):
                self._mark_first_audio(response_id)
                await self._send_client({
                    "type": "audio",
                    "data": event.get("delta", ""),
                })

            elif etype in ("response.audio_transcript.delta", "response.output_audio_transcript.delta"):
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
                await self._send_client({
                    "type": "transcript",
                    "role": "user",
                    "text": event.get("transcript", ""),
                })

            elif etype in ("response.function_call_arguments.done", "response.output_item.done"):
                if self._tool_logger:
                    self._tool_logger.info("TOOL_EVENT %s", json.dumps(event, ensure_ascii=False)[:2000])

                # Only function_call_arguments.done drives execution.
                if etype != "response.function_call_arguments.done":
                    continue

                _tool_name = event.get("name", "?")
                _tool_args = event.get("arguments", "{}")
                print(f"\n>>> TOOL CALL: {_tool_name}({_tool_args})\n")

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
                self._finish_response_metrics(response_id)
                self.current_response_id = None
                await self._send_client({
                    "type": "response_done",
                    "metrics": self._response_metrics.get(response_id, {}),
                })

            elif etype == "error":
                error = event.get("error", {})
                if await self._retry_session_update_after_schema_error(error):
                    continue
                log.error("OpenAI error: %s", event)
                await self._send_client({
                    "type": "error",
                    "message": str(error.get("message", "Unknown error")),
                    "code": error.get("code"),
                    "param": error.get("param"),
                })

    async def _handle_speech_started(self) -> None:
        self._turn_epoch += 1
        invalidated_response_id = self.current_response_id
        if invalidated_response_id:
            self._invalidated_response_ids.add(invalidated_response_id)

        log.info("Barge-in detected; invalidating response %s", invalidated_response_id)
        if self._bargein_logger:
            self._bargein_logger.info("BARGE_IN invalidated=%s epoch=%d", invalidated_response_id, self._turn_epoch)
        self._record_timeline("barge_in", response_id=invalidated_response_id)

        for task in list(self._tool_tasks):
            task.cancel()

        if invalidated_response_id:
            await self._send_openai({"type": "response.cancel"})

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

        should_respond = False
        try:
            if self._is_stale_tool_call(response_id, turn_epoch):
                log.info("Skipping stale tool call before execution: %s(%s)", tool_name, arguments)
                return

            log.info("Tool call: %s(%s)", tool_name, arguments)
            if self._tool_logger:
                self._tool_logger.info(
                    "TOOL_START name=%s call_id=%s args=%s",
                    tool_name, call_id, json.dumps(arguments, ensure_ascii=False),
                )
            tool_started_at = time.perf_counter()
            result: dict[str, Any]
            tool_duration_ms: float
            stale_after_execution = False

            try:
                async with self._tool_state_lock:
                    if self._is_stale_tool_call(response_id, turn_epoch):
                        log.info("Skipping stale tool call after lock: %s(%s)", tool_name, arguments)
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
                log.info("Tool call cancelled: %s", tool_name)
                raise

            if stale_after_execution:
                if self._tool_logger:
                    self._tool_logger.info(
                        "TOOL_STALE name=%s call_id=%s dur=%.1fms", tool_name, call_id, tool_duration_ms,
                    )
                log.info("Discarding stale tool result: %s(%s)", tool_name, arguments)
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

            if tool_name in ("filter_data", "append_visual"):
                if self._dashboard_logger:
                    self._dashboard_logger.info(
                        "VIEWS_UPDATE tool=%s args=%s",
                        tool_name, json.dumps(arguments, ensure_ascii=False),
                    )
                await self._send_client({
                    "type": "views_update",
                    "views": views,
                })

            await self._send_openai({
                "type": "conversation.item.create",
                "item": {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": self._tool_result_text(result, tool_duration_ms),
                },
            })

            await self._inject_context(updated_context)
            should_respond = True
        finally:
            # Only the tool call that empties the per-response pending count
            # actually fires response.create — prevents duplicate / racing
            # response.create when the model issues several tool calls in one turn.
            await self._finalize_tool_call(response_id, should_respond)

    async def _finalize_tool_call(self, response_id: str | None, should_respond: bool) -> None:
        if response_id is None:
            if should_respond:
                await self._send_openai({"type": "response.create"})
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
            await self._send_openai({"type": "response.create"})

    def _is_stale_tool_call(self, response_id: str | None, turn_epoch: int) -> bool:
        return (
            turn_epoch != self._turn_epoch
            or (response_id is not None and response_id in self._invalidated_response_ids)
            or not self._running
        )

    def _tool_result_text(self, result: dict[str, Any], duration_ms: float) -> str:
        return json.dumps({
            "success": result.get("success", False),
            "payload": result.get("payload"),
            "error": result.get("error"),
            "warning": result.get("warning"),
            "metrics": {
                "tool_duration_ms": duration_ms,
            },
        }, default=str)

    # ------------------------------------------------------------------
    # Context injection
    # ------------------------------------------------------------------

    async def _inject_context(self, text: str) -> None:
        """Inject a compact system-level dashboard context message."""
        await self._send_openai({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "system",
                "content": [{"type": "input_text", "text": text}],
            },
        })

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
        start_at = self._last_user_speech_stopped_at or self._last_manual_commit_at
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
        start_at = self._last_user_speech_stopped_at or self._last_manual_commit_at or metrics.get("created_at")
        metrics["ttfa_ms"] = round((now - start_at) * 1000, 2) if start_at else None
        metrics["response_created_to_first_audio_ms"] = (