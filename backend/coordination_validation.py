"""Deterministic checks for response-scoped realtime coordination."""

from __future__ import annotations

import asyncio

from response_coordinator import ResponseCoordinator


TOOLS = {"create_visual", "inspect_visual"}


def _response(response_id: str, call_id: str, name: str, arguments: str) -> dict:
    return {
        "id": response_id,
        "status": "completed",
        "output": [
            {
                "type": "function_call",
                "status": "completed",
                "call_id": call_id,
                "name": name,
                "arguments": arguments,
            }
        ],
    }


def validate_stale_response_is_rejected() -> None:
    coordinator = ResponseCoordinator()
    coordinator.bind_response("response-a")
    coordinator.register_tool_call(
        response_id="response-a",
        call_id="call-a",
        name="create_visual",
        arguments_raw='{"x":"state","y":"order_count"}',
    )
    coordinator.begin_user_turn()
    admission = coordinator.admit_tool_calls(
        _response(
            "response-a",
            "call-a",
            "create_visual",
            '{"x":"state","y":"order_count"}',
        ),
        allowed_tools=TOOLS,
        origin_user_transcript="old request",
    )
    assert not admission.allowed
    assert admission.reason in {"stale_intent_epoch", "response_not_current"}


def validate_completed_current_call_executes_once() -> None:
    coordinator = ResponseCoordinator()
    coordinator.begin_user_turn()
    coordinator.bind_response("response-b")
    arguments = '{"view_id":"view3"}'
    coordinator.register_tool_call(
        response_id="response-b",
        call_id="call-b",
        name="inspect_visual",
        arguments_raw=arguments,
    )
    response = _response(
        "response-b", "call-b", "inspect_visual", arguments
    )
    admission = coordinator.admit_tool_calls(
        response,
        allowed_tools=TOOLS,
        origin_user_transcript="inspect view three",
    )
    assert admission.allowed and len(admission.calls) == 1
    call = admission.calls[0]
    assert call.intent_epoch == coordinator.intent_epoch
    assert call.arguments == {"view_id": "view3"}
    coordinator.mark_executed(call)
    duplicate = coordinator.admit_tool_calls(
        response,
        allowed_tools=TOOLS,
        origin_user_transcript="inspect view three",
    )
    assert not duplicate.allowed
    assert duplicate.reason == "duplicate_call"


def validate_malformed_or_unknown_call_is_rejected() -> None:
    coordinator = ResponseCoordinator()
    coordinator.bind_response("response-c")
    coordinator.register_tool_call(
        response_id="response-c",
        call_id="call-c",
        name="unknown_tool",
        arguments_raw="not-json",
    )
    admission = coordinator.admit_tool_calls(
        _response("response-c", "call-c", "unknown_tool", "not-json"),
        allowed_tools=TOOLS,
        origin_user_transcript="bad call",
    )
    assert not admission.allowed
    assert admission.reason == "unknown_tool"


def validate_input_closed_and_followup_keep_epoch() -> None:
    coordinator = ResponseCoordinator()
    coordinator.begin_user_turn()
    epoch = coordinator.intent_epoch
    assert coordinator.begin_user_turn(input_closed=True) == epoch
    coordinator.prepare_followup(epoch)
    coordinator.bind_response("response-followup")
    assert coordinator.response_epoch("response-followup") == epoch


async def validate_response_reader_is_not_blocked_by_tools() -> None:
    from realtime import QwenRealtimeSession

    session = QwenRealtimeSession(client_ws=object())
    session.running = True
    session.current_response_id = "response-d"
    session.coordinator.bind_response("response-d")
    session.coordinator.register_tool_call(
        response_id="response-d",
        call_id="call-d",
        name="inspect_visual",
        arguments_raw='{"view_id":"view3"}',
    )
    release = asyncio.Event()

    async def send_client(_: dict) -> bool:
        return True

    async def blocked_batch(_: list) -> None:
        await release.wait()

    session._send_client = send_client  # type: ignore[method-assign]
    session._execute_tool_batch = blocked_batch  # type: ignore[method-assign]
    response = _response(
        "response-d", "call-d", "inspect_visual", '{"view_id":"view3"}'
    )
    await asyncio.wait_for(
        session._response_done({"type": "response.done", "response": response}),
        timeout=0.2,
    )
    assert session._tool_task is not None and not session._tool_task.done()
    release.set()
    await session._tool_task


def main() -> None:
    validate_stale_response_is_rejected()
    validate_completed_current_call_executes_once()
    validate_malformed_or_unknown_call_is_rejected()
    validate_input_closed_and_followup_keep_epoch()
    asyncio.run(validate_response_reader_is_not_blocked_by_tools())
    print("Response coordination validation passed.")


if __name__ == "__main__":
    main()
