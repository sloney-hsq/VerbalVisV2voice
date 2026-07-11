"""
Non-preemptive realtime runtime for VerbalVis-FD-Voice.

The existing Qwen realtime bridge remains responsible for the official event
flow and speech interruption behavior. This module adds a deliberately small
runtime boundary around local tools:

- a dispatched tool batch is allowed to finish;
- microphone chunks are ignored while that batch is running;
- tool arguments are bound to the user utterance that produced the batch;
- the browser receives explicit runtime and dashboard-state events;
- high-level comparison tools coexist with the primitive dashboard tools;
- there is no stale-tool invalidation, rollback, transaction, epoch, or thread
  cancellation.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocketDisconnect

from demo_tools import (
    execute_demo_tool,
    is_demo_tool,
    register_demo_tool_schemas,
)
from realtime import (
    QWEN_TURN_DETECTION,
    QwenRealtimeSession as BaseQwenRealtimeSession,
)
from tool_contracts import (
    batch_metadata,
    changes_dashboard,
    contract_for,
    result_summary,
)
from tools import (
    execute_tool,
    get_views_for_frontend,
    log_tool_call,
    normalize_tool_arguments,
    realtime_state,
)


@dataclass
class PendingToolCall:
    """A completed function call bound to its originating user utterance."""

    call_id: str
    name: str
    arguments_raw: str
    response_id: str | None
    origin_user_transcript: str


class QwenRealtimeSession(BaseQwenRealtimeSession):
    """Qwen session with a non-preemptive local-tool boundary."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.tool_running = False
        self._ignored_audio_chunks_during_tool = 0

    async def _configure_qwen_session(self) -> bool:
        register_demo_tool_schemas()
        configured = await super()._configure_qwen_session()
        if not configured:
            return False

        await self._send_client(
            {
                "type": "dashboard_state",
                "state": realtime_state(),
            }
        )
        await self._send_runtime_state("ready")
        return True

    async def _client_to_qwen(self) -> None:
        """Forward browser events while enforcing the tool-input gate."""
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
                    self._ignored_audio_chunks_during_tool += 1
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

    def _tool_calls_from_response(
        self,
        response: dict[str, Any],
    ) -> list[PendingToolCall]:
        """Extract calls and freeze the user utterance for the whole batch."""
        calls: list[PendingToolCall] = []
        response_id = str(response.get("id") or "") or None
        origin_user_transcript = self.last_user_transcript
        seen_call_ids: set[str] = set()

        for item in response.get("output") or []:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function_call":
                continue
            if item.get("status") not in {None, "completed"}:
                continue

            call_id = str(item.get("call_id") or "")
            name = str(item.get("name") or "")
            if not call_id or not name or call_id in seen_call_ids:
                continue
            seen_call_ids.add(call_id)

            arguments = item.get("arguments") or "{}"
            if not isinstance(arguments, str):
                arguments = json.dumps(arguments, ensure_ascii=False)

            calls.append(
                PendingToolCall(
                    call_id=call_id,
                    name=name,
                    arguments_raw=arguments,
                    response_id=response_id,
                    origin_user_transcript=origin_user_transcript,
                )
            )

        return calls

    async def _execute_tool_calls(
        self,
        calls: list[PendingToolCall],
    ) -> None:
        """Run one tool batch without accepting new microphone audio."""
        if not calls:
            return

        batch_response_id = calls[0].response_id
        batch_started_at = time.perf_counter()
        tool_meta = batch_metadata(call.name for call in calls)
        dashboard_will_change = any(
            changes_dashboard(call.name) for call in calls
        )

        self.tool_running = True
        self._ignored_audio_chunks_during_tool = 0
        completed_count = 0
        successful_count = 0
        followup_requested = False

        await self._send_client(
            {
                "type": "tool_execution_started",
                "response_id": batch_response_id,
                "tool_count": len(calls),
                "tools": tool_meta,
                "changes_dashboard": dashboard_will_change,
            }
        )
        await self._send_runtime_state(
            "updating_dashboard" if dashboard_will_change else "reading_dashboard",
            response_id=batch_response_id,
            tools=tool_meta,
        )
        self._append_jsonl(
            "tool_execution.jsonl",
            {
                "event": "tool_execution_started",
                "response_id": batch_response_id,
                "tool_count": len(calls),
                "tools": tool_meta,
                "changes_dashboard": dashboard_will_change,
            },
        )

        try:
            for pending in calls:
                result = await self._execute_one_tool(pending)
                completed_count += 1
                if result.get("success"):
                    successful_count += 1

            if self.running:
                # Keep the input gate closed until the post-tool response has
                # actually been requested from Qwen.
                followup_requested = await self._send_qwen(
                    {"type": "response.create"}
                )
        finally:
            total_duration_ms = round(
                (time.perf_counter() - batch_started_at) * 1000,
                2,
            )
            ignored_audio_chunks = self._ignored_audio_chunks_during_tool
            self.tool_running = False
            self._ignored_audio_chunks_during_tool = 0

            await self._send_client(
                {
                    "type": "tool_execution_finished",
                    "response_id": batch_response_id,
                    "tool_count": len(calls),
                    "completed_count": completed_count,
                    "successful_count": successful_count,
                    "failed_count": max(0, completed_count - successful_count),
                    "duration_ms": total_duration_ms,
                    "ignored_audio_chunks": ignored_audio_chunks,
                    "followup_requested": followup_requested,
                    "changes_dashboard": dashboard_will_change,
                    "tools": tool_meta,
                }
            )
            await self._send_client(
                {
                    "type": "dashboard_state",
                    "state": realtime_state(),
                }
            )
            await self._send_runtime_state(
                "processing" if followup_requested else "ready",
                response_id=batch_response_id,
                tools=tool_meta,
            )
            self._append_jsonl(
                "tool_execution.jsonl",
                {
                    "event": "tool_execution_finished",
                    "response_id": batch_response_id,
                    "tool_count": len(calls),
                    "completed_count": completed_count,
                    "successful_count": successful_count,
                    "failed_count": max(0, completed_count - successful_count),
                    "duration_ms": total_duration_ms,
                    "ignored_audio_chunks": ignored_audio_chunks,
                    "followup_requested": followup_requested,
                    "changes_dashboard": dashboard_will_change,
                },
            )

    async def _execute_one_tool(
        self,
        pending: PendingToolCall,
    ) -> dict[str, Any]:
        started_at = time.perf_counter()

        try:
            raw_arguments = json.loads(pending.arguments_raw or "{}")
            if not isinstance(raw_arguments, dict):
                raw_arguments = {}
        except json.JSONDecodeError:
            raw_arguments = {}

        arguments = normalize_tool_arguments(
            pending.name,
            raw_arguments,
            user_transcript=pending.origin_user_transcript,
        )
        arguments_json = json.dumps(arguments, ensure_ascii=False)

        await self._send_client(
            {
                "type": "tool_call",
                "name": pending.name,
                "arguments": arguments_json,
                "response_id": pending.response_id,
                "call_id": pending.call_id,
                "contract": contract_for(pending.name),
            }
        )

        if self._tool_logger:
            self._tool_logger.info(
                "TOOL_CALL_CREATED response_id=%s call_id=%s "
                "name=%s arguments=%s origin_user_transcript=%s",
                pending.response_id,
                pending.call_id,
                pending.name,
                pending.arguments_raw,
                pending.origin_user_transcript,
            )
            self._tool_logger.info(
                "TOOL_START response_id=%s name=%s call_id=%s args=%s",
                pending.response_id,
                pending.name,
                pending.call_id,
                arguments_json,
            )

        try:
            if is_demo_tool(pending.name):
                result = await asyncio.to_thread(
                    execute_demo_tool,
                    pending.name,
                    arguments,
                )
            else:
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

        await self._relay_tool_result(
            pending,
            result,
            duration_ms=duration_ms,
        )
        return result

    async def _relay_tool_result(
        self,
        pending: PendingToolCall,
        result: dict[str, Any],
        *,
        duration_ms: float,
    ) -> None:
        result = {
            "tool": pending.name,
            "success": bool(result.get("success")),
            "payload": result.get("payload"),
            "error": result.get("error"),
            "warning": result.get("warning"),
            **{
                key: value
                for key, value in result.items()
                if key not in {"tool", "success", "payload", "error", "warning"}
            },
        }
        summary = result_summary(pending.name, result)
        contract = contract_for(pending.name)

        await self._send_client(
            {
                "type": "tool_result",
                "response_id": pending.response_id,
                "call_id": pending.call_id,
                "duration_ms": duration_ms,
                "summary": summary,
                "contract": contract,
                **result,
            }
        )

        if result.get("success") and changes_dashboard(pending.name):
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
                    "source_tool": pending.name,
                    "call_id": pending.call_id,
                }
            )
            await self._send_client(
                {
                    "type": "dashboard_state",
                    "state": realtime_state(),
                    "source_tool": pending.name,
                    "call_id": pending.call_id,
                }
            )

        output = {
            "success": result.get("success", False),
            "tool": pending.name,
            "payload": result.get("payload"),
            "error": result.get("error"),
            "warning": result.get("warning"),
            "summary": summary,
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

    async def _send_runtime_state(
        self,
        phase: str,
        *,
        response_id: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        await self._send_client(
            {
                "type": "runtime_state",
                "phase": phase,
                "response_id": response_id,
                "tool_running": self.tool_running,
                "tools": tools or [],
            }
        )
