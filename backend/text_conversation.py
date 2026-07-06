"""
Turn-based text conversation manager for VerbalVis.

This shares the dashboard tool layer with the realtime voice session and only
replaces the interaction transport and turn-taking policy.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
import json
import logging
import os
import socket
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

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

_LOG_ROOT = Path(__file__).parent / "logs"
_LOG_ROOT.mkdir(exist_ok=True)
_LOG_FMT = logging.Formatter("%(asctime)s.%(msecs)03d  %(message)s", datefmt="%H:%M:%S")


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


QWEN_API_KEY = (
    os.getenv("QWEN_API_KEY")
    or os.getenv("DASHSCOPE_API_KEY")
    or ""
).strip()
QWEN_REGION = os.getenv("QWEN_REGION", "beijing").strip().lower()
QWEN_TEXT_MODEL = os.getenv("QWEN_TEXT_MODEL", os.getenv("QWEN_CHAT_MODEL", "qwen3.5-plus")).strip()
QWEN_TEXT_TEMPERATURE = float(os.getenv("QWEN_TEXT_TEMPERATURE", "0.2"))
QWEN_TEXT_TIMEOUT_SECONDS = float(os.getenv("QWEN_TEXT_TIMEOUT_SECONDS", "120"))
QWEN_TEXT_RETRY_ATTEMPTS = max(1, int(os.getenv("QWEN_TEXT_RETRY_ATTEMPTS", "2")))
QWEN_TEXT_RETRY_BACKOFF_SECONDS = float(os.getenv("QWEN_TEXT_RETRY_BACKOFF_SECONDS", "1.5"))
QWEN_TEXT_MAX_TOKENS = int(os.getenv("QWEN_TEXT_MAX_TOKENS", "900"))
QWEN_TEXT_ENABLE_THINKING = _env_bool("QWEN_TEXT_ENABLE_THINKING", False)
QWEN_TEXT_MAX_TOOL_ROUNDS = int(os.getenv("QWEN_TEXT_MAX_TOOL_ROUNDS", "8"))
QWEN_CHAT_COMPLETIONS_URL_OVERRIDE = os.getenv("QWEN_CHAT_COMPLETIONS_URL", "").strip()

MODEL_ONLY_TOOLS = {"inspect_visual"}
DASHBOARD_UPDATE_TOOLS = {
    "filter_data",
    "remove_filter",
    "append_visual",
    "delete_visual",
    "set_low_score_threshold",
    "highlight_visual",
}

NON_SUPERSEDING_TEXT_UTTERANCES = {
    "hi",
    "hello",
    "hey",
    "ok",
    "okay",
    "good",
    "right",
    "go on",
    "continue",
    "你好",
    "您好",
    "好的",
    "好",
    "嗯",
    "嗯嗯",
    "对",
    "对的",
    "继续",
    "你继续",
    "继续说",
}


def _normalize_text_utterance(text: str) -> str:
    text = " ".join((text or "").strip().lower().split())
    return text.strip("。！？!?.,，、")


def _is_non_superseding_text_utterance(text: str) -> bool:
    return _normalize_text_utterance(text) in NON_SUPERSEDING_TEXT_UTTERANCES


def _resolve_qwen_chat_completions_url() -> str:
    if QWEN_CHAT_COMPLETIONS_URL_OVERRIDE:
        return QWEN_CHAT_COMPLETIONS_URL_OVERRIDE
    if QWEN_REGION in {"singapore", "ap-southeast-1"}:
        host = "dashscope-intl.aliyuncs.com"
    else:
        host = "dashscope.aliyuncs.com"
    return f"https://{host}/compatible-mode/v1/chat/completions"


QWEN_CHAT_COMPLETIONS_URL = _resolve_qwen_chat_completions_url()


class QwenTextTimeoutError(RuntimeError):
    """Raised when DashScope does not return a chat completion in time."""


def _create_turn_id() -> str:
    return f"text-turn-{uuid.uuid4().hex[:10]}"


def _chat_tool_schemas() -> list[dict[str, Any]]:
    """Convert local flat tool schemas to OpenAI-compatible chat tools."""
    tools: list[dict[str, Any]] = []
    for tool in TOOL_SCHEMAS:
        nested_function = tool.get("function")
        function = nested_function if isinstance(nested_function, dict) else tool
        tools.append({
            "type": "function",
            "function": {
                "name": function.get("name"),
                "description": function.get("description", ""),
                "parameters": _chat_json_schema(function.get("parameters", {})),
            },
        })
    return tools


def _chat_json_schema(value: Any) -> Any:
    """Normalize nullable JSON Schema features for Qwen compatible mode."""
    if isinstance(value, list):
        return [_chat_json_schema(item) for item in value if item is not None]
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
            normalized[key] = _chat_json_schema(item)

    properties = normalized.get("properties")
    if isinstance(properties, dict):
        for prop in properties.values():
            if isinstance(prop, dict) and "type" not in prop and "enum" not in prop:
                prop["type"] = "string"

    return normalized


def _post_chat_completion(payload: dict[str, Any]) -> dict[str, Any]:
    if not QWEN_API_KEY:
        raise RuntimeError("QWEN_API_KEY or DASHSCOPE_API_KEY is not set.")

    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        QWEN_CHAT_COMPLETIONS_URL,
        data=body,
        headers={
            "Authorization": f"Bearer {QWEN_API_KEY}",
            "Content-Type": "application/json",
            "X-DashScope-DataInspection": "enable",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=QWEN_TEXT_TIMEOUT_SECONDS) as response:
            response_body = response.read().decode("utf-8")
            return json.loads(response_body)
    except (TimeoutError, socket.timeout) as exc:
        raise QwenTextTimeoutError(
            f"DashScope chat completion timed out after {QWEN_TEXT_TIMEOUT_SECONDS:g}s."
        ) from exc
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"DashScope chat completion failed with HTTP {exc.code}: {error_body[:1000]}"
        ) from exc
    except urllib.error.URLError as exc:
        if isinstance(getattr(exc, "reason", None), (TimeoutError, socket.timeout)):
            raise QwenTextTimeoutError(
                f"DashScope chat completion timed out after {QWEN_TEXT_TIMEOUT_SECONDS:g}s."
            ) from exc
        raise RuntimeError(f"DashScope chat completion request failed: {exc}") from exc


class QwenTextConversationSession:
    """One frontend client plus one turn-based text tool loop."""

    def __init__(
        self,
        client_ws: WebSocket,
        session_id: str = "default",
        model: str | None = None,
        analysis_id: str | None = None,
    ):
        self.client_ws = client_ws
        self.session_id = session_id
        self.analysis_id = safe_log_token(analysis_id) or None
        self.log_scope_id = self.analysis_id or safe_log_token(session_id, "session")
        self.model = model or QWEN_TEXT_MODEL
        self.is_processing = False
        self.current_turn_id: str | None = None
        self.messages: list[dict[str, Any]] = []
        self._turn_generation = 0
        self._interrupted_turn_ids: set[str] = set()
        self._turn_message_start: dict[str, int] = {}
        self._turn_user_texts: dict[str, str] = {}
        self._last_interrupted_user_text: str | None = None
        self._running = False
        self._turn_tasks: set[asyncio.Task] = set()
        self._tool_state_lock = asyncio.Lock()

        self._log_dir: Path | None = None
        self._event_logger: logging.Logger | None = None
        self._tool_logger: logging.Logger | None = None
        self._dashboard_logger: logging.Logger | None = None
        self._conversation_logger: logging.Logger | None = None

    async def start(self) -> None:
        init_views()
        self._running = True
        await self._send_session_snapshot()

        try:
            while self._running:
                raw = await self.client_ws.receive_text()
                msg = json.loads(raw)
                msg_type = msg.get("type", "?")
                self._log_event("CLIENT => %s", raw[:1000])

                if msg_type == "user_text":
                    await self._begin_text_turn(msg)
                elif msg_type == "start_session":
                    await self._reset_session()
                elif msg_type == "audio":
                    await self._send_client({
                        "type": "turn_rejected",
                        "reason": "text_session_does_not_accept_audio",
                    })
        except asyncio.CancelledError:
            raise
        except WebSocketDisconnect:
            self._log_event("CLIENT_DISCONNECTED")
        except Exception as exc:
            self._log_event("TEXT_SESSION_STOPPED %s", exc)
            await self._send_client({"type": "error", "message": str(exc)})
        finally:
            self._running = False
            await self._cancel_turn_tasks()

    async def _reset_session(self) -> None:
        if self.is_processing:
            await self._interrupt_current_text_turn("session_reset")
        self.messages = []
        self._clear_turn_tracking()
        init_views()
        await self._send_session_snapshot()

    async def _send_session_snapshot(self) -> None:
        payload = {
            "provider": "qwen",
            "model": self.model,
            "mode": "turn_based_text",
            "input_mode": "text",
            "turn_detection": "turn_based",
            "condition": "turn_based_text",
            "analysis_id": self.log_scope_id,
        }
        await self._send_client({
            "type": "init",
            "session_id": self.session_id,
            "views": get_views_for_frontend(),
            **payload,
        })
        await self._send_client({
            "type": "session_updated",
            "session_id": self.session_id,
            **payload,
        })
        await self._send_client({"type": "session_ready"})

    async def _begin_text_turn(self, msg: dict[str, Any]) -> None:
        user_text = str(msg.get("text") or "").strip()
        if not user_text:
            await self._send_client({
                "type": "turn_rejected",
                "reason": "empty_text",
            })
            return
        self._update_analysis_id_from_message(msg)
        self._init_session_loggers()
        if self.is_processing:
            await self._interrupt_current_text_turn("user_superseded_response")

        turn_id = str(msg.get("turn_id") or _create_turn_id())
        self._start_text_turn_task(user_text, turn_id)

    def _start_text_turn_task(self, user_text: str, turn_id: str) -> None:
        self._turn_generation += 1
        generation = self._turn_generation
        self.is_processing = True
        self.current_turn_id = turn_id
        self._turn_user_texts[turn_id] = user_text

        task = asyncio.create_task(
            self._run_text_turn(user_text, turn_id, generation),
            name=f"{self.session_id}:text_turn:{turn_id}",
        )
        self._turn_tasks.add(task)
        task.add_done_callback(self._turn_tasks.discard)

    async def _interrupt_current_text_turn(self, reason: str) -> None:
        interrupted_turn_id = self.current_turn_id
        if interrupted_turn_id:
            self._interrupted_turn_ids.add(interrupted_turn_id)
            self._ensure_turn_user_message(interrupted_turn_id)
            self._last_interrupted_user_text = self._turn_user_text(interrupted_turn_id)
            self._truncate_turn_messages(interrupted_turn_id)
            self._log_event("TEXT_TURN_INTERRUPTED turn_id=%s reason=%s", interrupted_turn_id, reason)
            await self._send_client({
                "type": "assistant_response_interrupted",
                "response_id": interrupted_turn_id,
                "turn_id": interrupted_turn_id,
                "reason": reason,
                "clear_queue": True,
            })

        self._turn_generation += 1
        self.is_processing = False
        self.current_turn_id = None

    def _is_current_turn(self, turn_id: str, generation: int) -> bool:
        return (
            self._running
            and self.current_turn_id == turn_id
            and self._turn_generation == generation
            and turn_id not in self._interrupted_turn_ids
        )

    async def _run_text_turn(self, user_text: str, turn_id: str, generation: int) -> None:
        started_at = time.perf_counter()
        response_started = False
        if not self._is_current_turn(turn_id, generation):
            self._interrupted_turn_ids.discard(turn_id)
            self._turn_message_start.pop(turn_id, None)
            self._turn_user_texts.pop(turn_id, None)
            return
        message_base_index = len(self.messages)
        self._turn_message_start[turn_id] = message_base_index
        try:
            self._log_conversation("You", user_text)
            turn_user_text = self._model_user_text(user_text)
            self.messages.append({"role": "user", "content": turn_user_text})
            if not self._is_current_turn(turn_id, generation):
                return

            await self._send_client({
                "type": "assistant_response_started",
                "response_id": turn_id,
                "turn_id": turn_id,
            })
            response_started = True

            for round_index in range(QWEN_TEXT_MAX_TOOL_ROUNDS):
                response = await self._call_text_model()
                if not self._is_current_turn(turn_id, generation):
                    return
                message = self._extract_message(response)
                tool_calls = self._extract_tool_calls(message)

                if not tool_calls:
                    assistant_text = self._message_text(message).strip()
                    if not assistant_text:
                        assistant_text = "I could not produce a text answer."
                    self.messages.append({"role": "assistant", "content": assistant_text})
                    self._log_conversation("AI", assistant_text)
                    if not self._is_current_turn(turn_id, generation):
                        return
                    await self._send_client({
                        "type": "transcript",
                        "role": "assistant",
                        "delta": assistant_text,
                        "response_id": turn_id,
                    })
                    break

                self.messages.append({
                    "role": "assistant",
                    "content": self._message_text(message),
                    "tool_calls": tool_calls,
                })

                for tool_call in tool_calls:
                    await self._execute_tool_call(
                        tool_call,
                        turn_id,
                        turn_user_text,
                        round_index,
                        generation,
                    )
                    if not self._is_current_turn(turn_id, generation):
                        return
            else:
                fallback = "I reached the tool-call limit before completing this turn."
                self.messages.append({"role": "assistant", "content": fallback})
                if not self._is_current_turn(turn_id, generation):
                    return
                await self._send_client({
                    "type": "transcript",
                    "role": "assistant",
                    "delta": fallback,
                    "response_id": turn_id,
                })
        except asyncio.CancelledError:
            if turn_id in self._interrupted_turn_ids:
                self._truncate_turn_messages(turn_id)
            raise
        except QwenTextTimeoutError as exc:
            if not self._is_current_turn(turn_id, generation):
                return
            log.warning("Text turn timed out: %s", exc)
            self._log_event("TEXT_TURN_TIMEOUT turn_id=%s %s", turn_id, exc)
            error_text = (
                "文本模型响应超时。我已保留当前仪表盘状态；请再试一次，"
                "或先缩小到一个维度继续分析。"
            )
            self.messages.append({"role": "assistant", "content": error_text})
            self._log_conversation("AI", error_text)
            if not response_started:
                await self._send_client({
                    "type": "assistant_response_started",
                    "response_id": turn_id,
                    "turn_id": turn_id,
                })
            await self._send_client({
                "type": "transcript",
                "role": "assistant",
                "delta": error_text,
                "response_id": turn_id,
            })
            await self._send_client({"type": "error", "message": str(exc)})
        except Exception as exc:
            if not self._is_current_turn(turn_id, generation):
                return
            log.exception("Text turn failed: %s", exc)
            error_text = f"Text model error: {exc}"
            self.messages.append({"role": "assistant", "content": error_text})
            if not response_started:
                await self._send_client({
                    "type": "assistant_response_started",
                    "response_id": turn_id,
                    "turn_id": turn_id,
                })
            await self._send_client({
                "type": "transcript",
                "role": "assistant",
                "delta": error_text,
                "response_id": turn_id,
            })
            await self._send_client({"type": "error", "message": str(exc)})
        finally:
            if turn_id in self._interrupted_turn_ids:
                self._interrupted_turn_ids.discard(turn_id)
                self._turn_message_start.pop(turn_id, None)
                self._turn_user_texts.pop(turn_id, None)
                return
            if not self._is_current_turn(turn_id, generation):
                self._turn_message_start.pop(turn_id, None)
                self._turn_user_texts.pop(turn_id, None)
                return
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            self.is_processing = False
            self.current_turn_id = None
            self._turn_message_start.pop(turn_id, None)
            self._turn_user_texts.pop(turn_id, None)
            self._last_interrupted_user_text = None
            await self._send_client({
                "type": "response_done",
                "response_id": turn_id,
                "turn_id": turn_id,
                "metrics": {"response_duration_ms": duration_ms},
            })

    def _model_user_text(self, user_text: str) -> str:
        if (
            self._last_interrupted_user_text
            and _is_non_superseding_text_utterance(user_text)
        ):
            return (
                f"{user_text}\n\n"
                "Continue answering the previous unanswered analytical request. "
                "Do not treat this short message as a new analysis goal."
            )
        return user_text

    def _ensure_turn_user_message(self, turn_id: str) -> None:
        if self._turn_message_start.get(turn_id) is not None:
            return
        user_text = self._turn_user_texts.get(turn_id)
        if not user_text:
            return
        self._turn_message_start[turn_id] = len(self.messages)
        self.messages.append({"role": "user", "content": user_text})

    def _turn_user_text(self, turn_id: str) -> str | None:
        start_index = self._turn_message_start.get(turn_id)
        if start_index is None or start_index >= len(self.messages):
            return None
        message = self.messages[start_index]
        if message.get("role") != "user":
            return None
        content = message.get("content")
        return content if isinstance(content, str) else None

    def _truncate_turn_messages(self, turn_id: str) -> None:
        start_index = self._turn_message_start.pop(turn_id, None)
        if start_index is None:
            return
        if start_index < len(self.messages) and self.messages[start_index].get("role") == "user":
            del self.messages[start_index + 1:]
        else:
            del self.messages[start_index:]

    def _clear_turn_tracking(self) -> None:
        self.is_processing = False
        self.current_turn_id = None
        self._interrupted_turn_ids.clear()
        self._turn_message_start.clear()
        self._turn_user_texts.clear()
        self._last_interrupted_user_text = None

    async def _call_text_model(self) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": self._build_instructions()},
                *self.messages[-30:],
            ],
            "tools": _chat_tool_schemas(),
            "tool_choice": "auto",
            "temperature": QWEN_TEXT_TEMPERATURE,
            "stream": False,
        }
        if QWEN_TEXT_MAX_TOKENS > 0:
            payload["max_tokens"] = QWEN_TEXT_MAX_TOKENS
        payload["enable_thinking"] = QWEN_TEXT_ENABLE_THINKING

        last_timeout: QwenTextTimeoutError | None = None
        for attempt in range(1, QWEN_TEXT_RETRY_ATTEMPTS + 1):
            self._log_event(
                "CHAT_COMPLETION_REQUEST messages=%d attempt=%d/%d timeout=%.1fs thinking=%s max_tokens=%s",
                len(payload["messages"]),
                attempt,
                QWEN_TEXT_RETRY_ATTEMPTS,
                QWEN_TEXT_TIMEOUT_SECONDS,
                QWEN_TEXT_ENABLE_THINKING,
                payload.get("max_tokens"),
            )
            try:
                response = await asyncio.to_thread(_post_chat_completion, payload)
            except QwenTextTimeoutError as exc:
                last_timeout = exc
                self._log_event(
                    "CHAT_COMPLETION_TIMEOUT attempt=%d/%d %s",
                    attempt,
                    QWEN_TEXT_RETRY_ATTEMPTS,
                    exc,
                )
                if attempt >= QWEN_TEXT_RETRY_ATTEMPTS:
                    raise
                await asyncio.sleep(QWEN_TEXT_RETRY_BACKOFF_SECONDS * attempt)
                continue

            self._log_event("CHAT_COMPLETION_RESPONSE %s", json.dumps(response, ensure_ascii=False)[:2000])
            return response

        if last_timeout:
            raise last_timeout
        raise RuntimeError("DashScope chat completion did not return a response.")

    def _build_instructions(self) -> str:
        state = json.dumps(
            realtime_state(),
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        return (
            f"{build_system_prompt('text_conversation')}\n\n"
            "CURRENT DASHBOARD METADATA (use this only to choose a relevant view; "
            "chart values require inspect_visual):\n"
            f"{state}"
        )

    async def _execute_tool_call(
        self,
        tool_call: dict[str, Any],
        turn_id: str,
        user_text: str,
        round_index: int,
        generation: int,
    ) -> None:
        if not self._is_current_turn(turn_id, generation):
            return
        self._init_session_loggers()

        call_id = str(tool_call.get("id") or f"{turn_id}-tool-{round_index}-{uuid.uuid4().hex[:6]}")
        raw_function = tool_call.get("function")
        function = raw_function if isinstance(raw_function, dict) else tool_call
        tool_name = str(function.get("name") or "")
        arguments = self._parse_tool_arguments(function.get("arguments"))
        arguments = normalize_tool_arguments(
            tool_name,
            arguments,
            user_transcript=user_text,
        )

        await self._send_client({
            "type": "tool_call",
            "name": tool_name,
            "arguments": json.dumps(arguments, ensure_ascii=False, default=str),
            "response_id": turn_id,
            "call_id": call_id,
        })
        if not self._is_current_turn(turn_id, generation):
            return

        tool_started_at = time.perf_counter()
        try:
            async with self._tool_state_lock:
                if not self._is_current_turn(turn_id, generation):
                    return
                result = await asyncio.to_thread(execute_tool, tool_name, arguments)
                views = get_views_for_frontend()
        except asyncio.CancelledError:
            tool_duration_ms = round((time.perf_counter() - tool_started_at) * 1000, 2)
            log_tool_call(
                session_id=self.session_id,
                analysis_id=self.log_scope_id,
                tool_name=tool_name,
                params=arguments,
                mode="turn_based_text",
                response_id=turn_id,
                call_id=call_id,
                result_success=False,
                cancelled=True,
                metrics={"tool_duration_ms": tool_duration_ms},
                log_dir=self._log_dir,
            )
            raise

        if not self._is_current_turn(turn_id, generation):
            log_tool_call(
                session_id=self.session_id,
                analysis_id=self.log_scope_id,
                tool_name=tool_name,
                params=arguments,
                mode="turn_based_text",
                response_id=turn_id,
                call_id=call_id,
                result_success=result.get("success"),
                cancelled=True,
                metrics={"tool_duration_ms": round((time.perf_counter() - tool_started_at) * 1000, 2)},
                log_dir=self._log_dir,
            )
            return

        tool_duration_ms = round((time.perf_counter() - tool_started_at) * 1000, 2)
        self._log_tool(
            "TOOL_DONE name=%s call_id=%s dur=%.1fms success=%s",
            tool_name,
            call_id,
            tool_duration_ms,
            result.get("success"),
        )
        log_tool_call(
            session_id=self.session_id,
            analysis_id=self.log_scope_id,
            tool_name=tool_name,
            params=arguments,
            mode="turn_based_text",
            response_id=turn_id,
            call_id=call_id,
            result_success=result.get("success"),
            cancelled=False,
            metrics={"tool_duration_ms": tool_duration_ms},
            log_dir=self._log_dir,
        )

        if tool_name not in MODEL_ONLY_TOOLS:
            await self._send_client({
                "type": "tool_result",
                "response_id": turn_id,
                "call_id": call_id,
                "duration_ms": tool_duration_ms,
                **result,
            })

        if tool_name in DASHBOARD_UPDATE_TOOLS:
            self._log_dashboard("VIEWS_UPDATE tool=%s", tool_name)
            await self._send_client({"type": "views_update", "views": views})

        self.messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": self._tool_result_text(result),
        })

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

    def _extract_message(self, response: dict[str, Any]) -> dict[str, Any]:
        choices = response.get("choices")
        if not choices:
            raise RuntimeError("Text model returned no choices.")
        message = choices[0].get("message")
        if not isinstance(message, dict):
            raise RuntimeError("Text model returned no message.")
        return message

    def _extract_tool_calls(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        tool_calls = message.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            return tool_calls
        function_call = message.get("function_call")
        if isinstance(function_call, dict):
            return [{
                "id": f"legacy-call-{uuid.uuid4().hex[:8]}",
                "type": "function",
                "function": function_call,
            }]
        return []

    def _message_text(self, message: dict[str, Any]) -> str:
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    parts.append(item["text"])
            return "".join(parts)
        return ""

    def _parse_tool_arguments(self, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if not value:
            return {}
        try:
            parsed = json.loads(str(value))
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _init_session_loggers(self) -> None:
        if self._log_dir:
            return
        log_dir, log_scope_id = resolve_session_log_dir(
            _LOG_ROOT,
            session_id=self.session_id,
            mode="text",
            analysis_id=self.analysis_id,
        )
        self._log_dir = log_dir
        self.log_scope_id = log_scope_id

        def _make(name: str) -> logging.Logger:
            logger = logging.getLogger(f"text_conversation.{name}.{self.session_id}.{self.log_scope_id}")
            logger.setLevel(logging.DEBUG)
            logger.propagate = False
            logger.handlers.clear()
            fh = logging.FileHandler(log_dir / f"{name}.log", encoding="utf-8")
            fh.setFormatter(_LOG_FMT)
            logger.addHandler(fh)
            return logger

        self._event_logger = _make("text_events")
        self._tool_logger = _make("tool_calls")
        self._dashboard_logger = _make("dashboard")
        self._conversation_logger = _make("conversation")

    async def _cancel_turn_tasks(self) -> None:
        for task in list(self._turn_tasks):
            task.cancel()
        if self._turn_tasks:
            await asyncio.gather(*self._turn_tasks, return_exceptions=True)
        self._turn_tasks.clear()
        self._clear_turn_tracking()

    def _log_event(self, message: str, *args: Any) -> None:
        if self._event_logger:
            self._event_logger.info(message, *args)

    def _log_tool(self, message: str, *args: Any) -> None:
        if self._tool_logger:
            self._tool_logger.info(message, *args)

    def _log_dashboard(self, message: str, *args: Any) -> None:
        if self._dashboard_logger:
            self._dashboard_logger.info(message, *args)

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

    async def _send_client(self, msg: dict[str, Any]) -> None:
        try:
            await self.client_ws.send_json(msg)
        except Exception as exc:
            log.debug("Failed to send client message: %s", exc)
