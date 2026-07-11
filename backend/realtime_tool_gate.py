"""Minimal non-preemptive tool gate for VerbalVis FD-Voice.

This module keeps the existing Qwen realtime bridge intact and adds one narrow
runtime boundary: once a dashboard tool batch starts, new browser audio chunks
are ignored until the batch finishes. Tool calls are not cancelled, rolled
back, or invalidated.
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import WebSocketDisconnect

from realtime import (
    DASHBOARD_TOOLS,
    QWEN_TURN_DETECTION,
    PendingToolCall,
    QwenRealtimeSession as BaseQwenRealtimeSession,
)
from tools import (
    execute_tool,
    get_views_for_frontend,
    log_tool_call,
    normalize_tool_arguments,
    realtime_state,
)


class QwenRealtimeSession(BaseQwenRealtimeSession):
    """Qwen realtime session with a small non-preemptive tool boundary."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.tool_running = False

    async def _client_to_qwen(self) -> None:
        """Forward browser events, dropping audio only while tools are running."""
        while self.running:
            try:
                raw = await self.client_ws.receive_text()
            except WebSocketDisconnect:
                self.running = False
                self._log_connection("CLIENT_DISCONNECTED")
                return
            except RuntimeError as exc:
                if self._is_client_disconnect_error(exc):
                    self.running = False
                    self._log_connection(
                        "CLIENT_DISCONNECTED %s",
                        exc,
                    )
                    return
                raise

            message = json.loads(raw)
            message_type = message.get("type", "")

            if message_type == "audio":
                if self.tool_running:
                    continue
                audio = message.get("data")
                if audio:
                    await self._send_qwen(
                        {
                            "type": "input_audio_buffer.append",
                            "audio": audio,
                        }
                    )

            elif message_type == "playback_stopped":
                self._handle_playback_stopped(message)

            elif message_type in {"close", "disconnect"}:
                self.running = False
                return

    async def _execute_tool_calls(
        self,
        calls: list[PendingToolCall],
    ) -> None:
        """Run a tool batch atomically from the interaction perspective.

        The tool batch uses the user transcript that was current when execution
        started. New microphone audio is ignored until all calls finish. This is
        intentionally not stale-tool invalidation: dispatched tools are allowed
        to complete normally.
        """
        if not calls:
            return

        origin_user_transcript = self.last_user_transcript
        batch_response_id = calls[0].response_id
        self.tool_running = True

        await self._send_client(
            {
                "type": "tool_execution_started",
                "response_id": batch_response_id,
                "tool_count": len(calls),
            }
        )

        try:
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
                    user_transcript=origin_user_transcript,
                )
                arguments_json = json.dumps(arguments, ensure_ascii=False)

                await self._send_client(
                    {
                        "type": "tool_call",
                        "name": pending.name,
                        "arguments": arguments_json,
                        "response_id": pending.response_id,
                        "call_id": pending.call_id,
                    }
                )

                if self._tool_logger:
                    self._tool_logger.info(
                        "TOOL_CALL_CREATED response_id=%s call_id=%s "
                        "name=%s arguments=%s",
                        pending.response_id,
                        pending.call_id,
                        pending.name,
                        pending.arguments_raw,
                    )
                    self._tool_logger.info(
                        "TOOL_START response_id=%s name=%s call_id=%s args=%s",
                        pending.response_id,
                        pending.name,
                        pending.call_id,
                        arguments_json,
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
                        "TOOL_DONE response_id=%s name=%s call_id=%s "
                        "duration_ms=%s success=%s",
                        pending.response_id,
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
        finally:
            self.tool_running = False
            await self._send_client(
                {
                    "type": "tool_execution_finished",
                    "response_id": batch_response_id,
                    "tool_count": len(calls),
                }
            )

        if self.running:
            await self._send_qwen({"type": "response.create"})
