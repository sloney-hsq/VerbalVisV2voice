"""Small, testable state machine for response-scoped tool admission.

The coordinator does not execute tools or own network I/O.  It only answers
whether a completed Realtime response is still entitled to submit its calls.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Iterable


@dataclass(frozen=True)
class PendingToolCall:
    call_id: str
    name: str
    arguments_raw: str
    arguments: dict[str, Any]
    response_id: str
    intent_epoch: int
    origin_user_transcript: str = ""


@dataclass(frozen=True)
class ToolAdmission:
    allowed: bool
    reason: str
    calls: tuple[PendingToolCall, ...] = ()


class ResponseCoordinator:
    """Track current intent, response ownership, and exactly-once calls."""

    def __init__(self) -> None:
        self.intent_epoch = 0
        self.current_response_id: str | None = None
        self._response_epochs: dict[str, int] = {}
        self._pending: dict[tuple[str, str], PendingToolCall] = {}
        self._executed: set[tuple[str, str]] = set()
        self._interrupted: set[str] = set()
        self._followup_epoch: int | None = None

    def begin_user_turn(self, *, input_closed: bool = False) -> int:
        if input_closed:
            return self.intent_epoch
        if self.current_response_id:
            self._interrupted.add(self.current_response_id)
        self.current_response_id = None
        self._followup_epoch = None
        self.intent_epoch += 1
        return self.intent_epoch

    def bind_response(self, response_id: str) -> int:
        epoch = (
            self._followup_epoch
            if self._followup_epoch is not None
            else self.intent_epoch
        )
        self._followup_epoch = None
        self._response_epochs[response_id] = epoch
        self.current_response_id = response_id
        return epoch

    def interrupt_current(self) -> str | None:
        response_id = self.current_response_id
        if response_id:
            self._interrupted.add(response_id)
            self.current_response_id = None
        return response_id

    def prepare_followup(self, epoch: int) -> None:
        self._followup_epoch = epoch

    def response_epoch(self, response_id: str) -> int | None:
        return self._response_epochs.get(response_id)

    def register_tool_call(
        self,
        *,
        response_id: str,
        call_id: str,
        name: str,
        arguments_raw: str,
        origin_user_transcript: str = "",
    ) -> bool:
        if not response_id or not call_id or not name:
            return False
        epoch = self._response_epochs.get(response_id)
        if epoch is None:
            return False
        arguments = self._parse_arguments(arguments_raw)
        if arguments is None:
            # Preserve the record so admission can return a deterministic
            # malformed-arguments reason after checking the tool name.
            arguments = {}
        self._pending[(response_id, call_id)] = PendingToolCall(
            call_id=call_id,
            name=name,
            arguments_raw=arguments_raw,
            arguments=arguments,
            response_id=response_id,
            intent_epoch=epoch,
            origin_user_transcript=origin_user_transcript,
        )
        return True

    def admit_tool_calls(
        self,
        response: dict[str, Any],
        *,
        allowed_tools: Iterable[str],
        origin_user_transcript: str,
    ) -> ToolAdmission:
        response_id = str(response.get("id") or "")
        if not response_id or response.get("status") != "completed":
            return ToolAdmission(False, "response_not_completed")
        epoch = self._response_epochs.get(response_id)
        if epoch is None or epoch != self.intent_epoch:
            return ToolAdmission(False, "stale_intent_epoch")
        if response_id in self._interrupted:
            return ToolAdmission(False, "response_interrupted")
        if response_id != self.current_response_id:
            return ToolAdmission(False, "response_not_current")

        allowed = set(allowed_tools)
        calls: list[PendingToolCall] = []
        seen: set[str] = set()
        for item in response.get("output") or []:
            if not isinstance(item, dict) or item.get("type") != "function_call":
                continue
            if item.get("status") not in {None, "completed"}:
                return ToolAdmission(False, "call_not_completed")
            call_id = str(item.get("call_id") or "")
            name = str(item.get("name") or "")
            if not call_id or not name or call_id in seen:
                return ToolAdmission(False, "invalid_call_identity")
            seen.add(call_id)
            if name not in allowed:
                return ToolAdmission(False, "unknown_tool")
            key = (response_id, call_id)
            if key in self._executed:
                return ToolAdmission(False, "duplicate_call")
            pending = self._pending.get(key)
            if pending is None:
                return ToolAdmission(False, "missing_arguments_done")
            response_raw = item.get("arguments") or "{}"
            if not isinstance(response_raw, str):
                response_raw = json.dumps(response_raw, ensure_ascii=False)
            response_arguments = self._parse_arguments(response_raw)
            authoritative_arguments = self._parse_arguments(pending.arguments_raw)
            if response_arguments is None or authoritative_arguments is None:
                return ToolAdmission(False, "malformed_arguments")
            if pending.name != name or response_arguments != authoritative_arguments:
                return ToolAdmission(False, "call_mismatch")
            calls.append(
                PendingToolCall(
                    call_id=pending.call_id,
                    name=pending.name,
                    arguments_raw=pending.arguments_raw,
                    arguments=authoritative_arguments,
                    response_id=response_id,
                    intent_epoch=epoch,
                    origin_user_transcript=origin_user_transcript,
                )
            )
        if not calls:
            return ToolAdmission(False, "no_tool_calls")
        return ToolAdmission(True, "admitted", tuple(calls))

    def mark_executed(self, call: PendingToolCall) -> None:
        self._executed.add((call.response_id, call.call_id))

    def complete_response(self, response_id: str) -> None:
        if self.current_response_id == response_id:
            self.current_response_id = None

    @staticmethod
    def _parse_arguments(value: str) -> dict[str, Any] | None:
        try:
            parsed = json.loads(value or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            return None
        return parsed if isinstance(parsed, dict) else None
