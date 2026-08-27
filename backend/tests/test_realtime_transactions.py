from __future__ import annotations

import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sys
from threading import Event


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import realtime
from response_coordinator import PendingToolCall
from runtime.transactions import ResponseStatus
from tools import (
    apply_dashboard_snapshot,
    capture_dashboard_snapshot,
    execute_tool_in_snapshot,
)


class _ClientSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send_json(self, payload: dict[str, object]) -> None:
        self.messages.append(deepcopy(payload))


class _QwenSocket:
    def __init__(self) -> None:
        self.messages: list[dict[str, object]] = []

    async def send(self, raw: str) -> None:
        self.messages.append(json.loads(raw))


def _session(*, status: ResponseStatus) -> realtime.QwenRealtimeSession:
    client = _ClientSocket()
    session = realtime.QwenRealtimeSession(client, session_id="test")
    session.running = True
    session.qwen_ws = _QwenSocket()
    session.dashboard_store = realtime.DashboardStore(
        capture_dashboard_snapshot(), intent_epoch=0
    )
    session.coordinator.bind_response("response-1")
    transaction = session.transactions.begin_response(
        "response-1", base_revision=session.dashboard_store.revision
    )
    transaction.status = status
    session.current_response_id = (
        "response-1" if status is ResponseStatus.STREAMING else None
    )
    if status is ResponseStatus.EXECUTING_DRAFT:
        session.coordinator.complete_response("response-1")
    return session


def _call(call_id: str, *, epoch: int = 0) -> PendingToolCall:
    return PendingToolCall(
        call_id=call_id,
        name="highlight_visual",
        arguments_raw='{"action":"clear"}',
        arguments={"action": "clear"},
        response_id="response-1",
        intent_epoch=epoch,
        origin_user_transcript="clear highlights",
    )


def test_speech_start_marks_overlap_without_cancelling_response() -> None:
    async def scenario() -> None:
        session = _session(status=ResponseStatus.STREAMING)

        await session._speech_started({"item_id": "utterance-1"})

        assert session.transactions.intent_epoch == 0
        assert session.coordinator.intent_epoch == 0
        assert session.current_response_id == "response-1"
        assert not any(
            message.get("type") == "response.cancel"
            for message in session.qwen_ws.messages
        )
        assert any(
            message.get("type") == "response_overlap"
            and message.get("response_id") == "response-1"
            for message in session.client_ws.messages
        )

    asyncio.run(scenario())


def test_snapshot_tool_execution_restores_committed_globals() -> None:
    """A legacy handler may mutate only its private draft until CAS succeeds."""
    baseline = capture_dashboard_snapshot()
    committed = deepcopy(baseline)
    committed["highlighted_views"] = ["committed-view"]
    draft = deepcopy(committed)
    draft["highlighted_views"] = ["draft-view"]
    apply_dashboard_snapshot(committed)
    try:
        result, next_snapshot = execute_tool_in_snapshot(
            "highlight_visual",
            {"action": "clear"},
            draft,
        )
        assert result["success"] is True
        assert next_snapshot["highlighted_views"] == []
        assert capture_dashboard_snapshot()["highlighted_views"] == [
            "committed-view"
        ]
    finally:
        apply_dashboard_snapshot(baseline)


def test_backchannel_resumes_overlap_without_superseding_response() -> None:
    async def scenario() -> None:
        session = _session(status=ResponseStatus.STREAMING)

        await session._speech_started({"item_id": "utterance-1"})
        await session._user_transcript_completed(
            {"item_id": "utterance-1", "transcript": "yes, continue"}
        )

        assert session.transactions.intent_epoch == 0
        assert session.transactions.get("response-1").status is ResponseStatus.STREAMING
        assert session.current_response_id == "response-1"
        assert not any(
            message.get("type") == "response.cancel"
            for message in session.qwen_ws.messages
        )
        assert any(
            message.get("type") == "response_resumed"
            and message.get("decision") == "BACKCHANNEL"
            for message in session.client_ws.messages
        )

    asyncio.run(scenario())


def test_stop_only_cancels_without_advancing_analytical_epoch() -> None:
    async def scenario() -> None:
        session = _session(status=ResponseStatus.STREAMING)

        await session._speech_started({"item_id": "utterance-1"})
        await session._user_transcript_completed(
            {"item_id": "utterance-1", "transcript": "stop"}
        )

        assert session.transactions.intent_epoch == 0
        assert session.coordinator.intent_epoch == 0
        assert session.transactions.get("response-1").status is ResponseStatus.CANCELLED
        assert any(
            message.get("type") == "response.cancel"
            for message in session.qwen_ws.messages
        )
        assert any(
            message.get("type") == "response_cancelled"
            and message.get("reason") == "stop_only"
            for message in session.client_ws.messages
        )

    asyncio.run(scenario())


def test_completed_backchannel_keeps_finished_draft_eligible_for_commit(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        session = _session(status=ResponseStatus.EXECUTING_DRAFT)
        staged = Event()
        monkeypatch.setattr(
            realtime,
            "realtime_state",
            lambda: {
                "dashboard_revision": capture_dashboard_snapshot()["dashboard_revision"],
                "filters": [],
                "highlighted": [],
                "views": [],
            },
        )
        def draft_tool(name, arguments, snapshot):
            staged.set()
            return (
                {"tool": name, "success": True, "payload": {}},
                deepcopy(snapshot),
            )
        monkeypatch.setattr(realtime, "execute_tool_in_snapshot", draft_tool)

        await session._speech_started({"item_id": "utterance-1"})
        task = asyncio.create_task(session._execute_tool_batch([_call("call-1")]))
        assert await asyncio.to_thread(staged.wait, 1)
        assert not task.done()

        await session._user_transcript_completed(
            {"item_id": "utterance-1", "transcript": "yes, continue"}
        )
        await task

        finished = [
            message
            for message in session.client_ws.messages
            if message.get("type") == "tool_execution_finished"
        ]
        assert finished[0]["commit_status"] == "committed"
        assert any(
            message.get("type") == "dashboard_commit"
            for message in session.client_ws.messages
        )

    asyncio.run(scenario())


def test_transaction_is_finalized_before_dashboard_socket_publication(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        session = _session(status=ResponseStatus.EXECUTING_DRAFT)
        monkeypatch.setattr(
            realtime,
            "realtime_state",
            lambda: {
                "dashboard_revision": capture_dashboard_snapshot()["dashboard_revision"],
                "filters": [],
                "highlighted": [],
                "views": [],
            },
        )
        original_send = session._send_client
        commit_started = asyncio.Event()
        release_commit = asyncio.Event()

        async def blocked_send(payload):
            if payload.get("type") == "dashboard_commit":
                commit_started.set()
                await release_commit.wait()
            return await original_send(payload)

        monkeypatch.setattr(session, "_send_client", blocked_send)
        task = asyncio.create_task(session._execute_tool_batch([_call("call-1")]))
        await asyncio.wait_for(commit_started.wait(), timeout=1)

        assert session.transactions.current_response_id is None
        assert session.transactions.get("response-1").status is ResponseStatus.COMMITTED

        release_commit.set()
        await task

    asyncio.run(scenario())


def test_analytical_revision_discards_inflight_draft(monkeypatch) -> None:
    async def scenario() -> None:
        baseline = capture_dashboard_snapshot()
        apply_dashboard_snapshot({**baseline, "dashboard_revision": 0})
        session = _session(status=ResponseStatus.EXECUTING_DRAFT)
        started = Event()
        release = Event()

        def delayed_draft_tool(name, arguments, snapshot):
            next_snapshot = deepcopy(snapshot)
            next_snapshot["highlighted_views"] = ["draft-only"]
            started.set()
            assert release.wait(5)
            return (
                {"tool": name, "success": True, "payload": {"draft": True}},
                next_snapshot,
            )

        monkeypatch.setattr(
            realtime, "execute_tool_in_snapshot", delayed_draft_tool
        )
        task = asyncio.create_task(session._execute_tool_batch([_call("call-1")]))
        assert await asyncio.to_thread(started.wait, 5)

        await session._speech_started({"item_id": "utterance-2"})
        await session._user_transcript_completed(
            {
                "item_id": "utterance-2",
                "transcript": "instead show monthly revenue",
            }
        )
        release.set()
        await task

        assert session.transactions.intent_epoch == 1
        assert session.coordinator.intent_epoch == 1
        assert capture_dashboard_snapshot()["highlighted_views"] == baseline[
            "highlighted_views"
        ]
        assert not any(
            message.get("type") == "dashboard_commit"
            for message in session.client_ws.messages
        )
        finished = [
            message
            for message in session.client_ws.messages
            if message.get("type") == "tool_execution_finished"
        ]
        assert len(finished) == 1
        assert finished[0]["commit_status"] == "stale_discarded"
        assert not any(
            message.get("type") == "conversation.item.create"
            for message in session.qwen_ws.messages
        )

        apply_dashboard_snapshot(baseline)

    asyncio.run(scenario())


def test_valid_mutation_batch_commits_once_and_publishes_outputs_in_order(
    monkeypatch,
) -> None:
    async def scenario() -> None:
        baseline = capture_dashboard_snapshot()
        apply_dashboard_snapshot({**baseline, "dashboard_revision": 0})
        session = _session(status=ResponseStatus.EXECUTING_DRAFT)

        def draft_tool(name, arguments, snapshot):
            next_snapshot = deepcopy(snapshot)
            next_snapshot["highlight_element"] = arguments.get("marker")
            return (
                {
                    "tool": name,
                    "success": True,
                    "payload": {"marker": arguments.get("marker")},
                },
                next_snapshot,
            )

        monkeypatch.setattr(realtime, "execute_tool_in_snapshot", draft_tool)
        monkeypatch.setattr(
            realtime,
            "realtime_state",
            lambda: {
                "dashboard_revision": capture_dashboard_snapshot()["dashboard_revision"],
                "filters": [],
                "highlighted": [],
                "views": [],
            },
        )
        calls = [
            PendingToolCall(
                **{
                    **_call("call-1").__dict__,
                    "arguments": {"action": "clear", "marker": "first"},
                }
            ),
            PendingToolCall(
                **{
                    **_call("call-2").__dict__,
                    "arguments": {"action": "clear", "marker": "second"},
                }
            ),
        ]

        await session._execute_tool_batch(calls)

        commits = [
            message
            for message in session.client_ws.messages
            if message.get("type") == "dashboard_commit"
        ]
        assert len(commits) == 1
        assert commits[0]["dashboard_revision"] == 1
        assert capture_dashboard_snapshot()["dashboard_revision"] == 1
        assert capture_dashboard_snapshot()["highlight_element"] == "second"
        outputs = [
            message
            for message in session.qwen_ws.messages
            if message.get("type") == "conversation.item.create"
        ]
        assert [message["item"]["call_id"] for message in outputs] == [
            "call-1",
            "call-2",
        ]
        assert session.qwen_ws.messages[-1]["type"] == "response.create"

        apply_dashboard_snapshot(baseline)

    asyncio.run(scenario())
