import builtins
from concurrent.futures import ThreadPoolExecutor
import json
from datetime import datetime, timezone
from threading import Barrier

import pytest

from dataops_agent.runtime.context import ContextManager
from dataops_agent.runtime.state import InMemoryStateStore, RedisStateStore
from dataops_agent.runtime.tools import ToolRegistry, ToolSpec
from dataops_agent.runtime.tracing import JsonlTracer


def test_registry_returns_the_registered_tool_spec():
    """Removing the registry mapping would make registered tools unavailable."""
    spec = ToolSpec(
        name="quality_report",
        description="Return data-quality metrics.",
        handler=lambda: {"valid": True},
    )
    registry = ToolRegistry()

    registry.register(spec)

    assert registry.get("quality_report") is spec
    assert registry.names() == ("quality_report",)


def test_registry_rejects_duplicate_or_malformed_tool_names():
    """Permissive registration would make dispatch names ambiguous or invalid."""
    registry = ToolRegistry()
    registry.register(ToolSpec(name="quality_report", description="Report.", handler=lambda: None))

    with pytest.raises(ValueError, match="already registered"):
        registry.register(ToolSpec(name="quality_report", description="Again.", handler=lambda: None))
    with pytest.raises(ValueError, match="tool name"):
        ToolSpec(name="not a tool", description="Invalid.", handler=lambda: None)


def test_newer_response_claim_rejects_stale_tool_execution():
    """Dropping response ownership checks would permit a superseded response."""
    store = InMemoryStateStore()
    stale_epoch = store.claim_response("session-1", "response-1")
    current_epoch = store.claim_response("session-1", "response-2")

    assert (stale_epoch, current_epoch) == (1, 2)
    assert not store.admit_tool("session-1", "response-1", stale_epoch)
    assert store.admit_tool("session-1", "response-2", current_epoch)


def test_idempotency_key_can_only_be_claimed_once():
    """Removing atomic claims would allow a mutating request to run twice."""
    store = InMemoryStateStore()

    assert store.claim_idempotency("load:batch-7")
    assert not store.claim_idempotency("load:batch-7")


def test_concurrent_response_claims_receive_unique_monotonic_epochs():
    """A read-modify-write race would let concurrent claims return the same epoch."""
    store = InMemoryStateStore()
    store._epochs = _InterleavingEpochs()  # Force both unprotected reads to see epoch zero.

    with ThreadPoolExecutor(max_workers=2) as executor:
        epochs = list(executor.map(lambda index: store.claim_response("session-1", f"response-{index}"), range(2)))

    assert sorted(epochs) == [1, 2]


def test_concurrent_idempotency_claims_have_exactly_one_winner():
    """A check-then-add race would allow the same mutation to be claimed twice."""
    store = InMemoryStateStore()
    store._idempotency_keys = _InterleavingKeys()  # Force both unprotected membership checks to miss.

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(lambda _: store.claim_idempotency("load:batch-8"), range(2)))

    assert sorted(claims) == [False, True]


def test_redis_store_is_lazy_when_given_a_client_factory():
    """Eager Redis construction would make offline unit tests contact Redis."""
    constructed = []

    def factory():
        constructed.append(True)
        raise AssertionError("the client should not be constructed yet")

    RedisStateStore(client_factory=factory)

    assert constructed == []


def test_redis_state_store_uses_injected_client_for_epochs_and_idempotency():
    """Incorrect Redis commands would admit stale work or duplicate a mutation."""
    store = RedisStateStore(client=_FakeRedis(), key_prefix="test-runtime")
    stale_epoch = store.claim_response("session-1", "response-1")
    current_epoch = store.claim_response("session-1", "response-2")

    assert (stale_epoch, current_epoch) == (1, 2)
    assert not store.admit_tool("session-1", "response-1", stale_epoch)
    assert store.admit_tool("session-1", "response-2", current_epoch)
    assert store.claim_idempotency("load:batch-9")
    assert not store.claim_idempotency("load:batch-9")


def test_redis_state_store_explains_missing_redis_dependency(monkeypatch):
    """Without redis-py, an uninjected adapter must fail clearly only when used."""
    real_import = builtins.__import__

    def import_without_redis(name, *args, **kwargs):
        if name == "redis":
            raise ModuleNotFoundError("No module named 'redis'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", import_without_redis)

    with pytest.raises(RuntimeError, match="requires redis-py"):
        RedisStateStore().claim_idempotency("load:batch-10")


def test_context_manager_keeps_newest_complete_messages_within_budget():
    """Keeping oldest messages or overflowing the budget would lose current context."""
    manager = ContextManager(max_characters=10)

    compacted = manager.compact(["12345", "67890", "xy"])

    assert compacted == ["67890", "xy"]
    assert sum(len(message) for message in compacted) <= 10


def test_context_manager_does_not_skip_an_oversized_message_to_keep_older_ones():
    """Skipping the middle message would return a non-contiguous, misleading history."""
    compacted = ContextManager(max_characters=6).compact(["old", "123456789", "new"])

    assert compacted == ["new"]


def test_jsonl_tracer_writes_one_safe_json_event(tmp_path):
    """Unsafe serialization or secret leakage would break durable trace output."""
    path = tmp_path / "trace.jsonl"
    tracer = JsonlTracer(path)

    tracer.emit(
        {
            "trace_id": "trace-1",
            "session_id": "session-1",
            "call_id": "call-1",
            "tool_name": "quality_report",
            "status": "completed",
            "elapsed_ms": 7,
            "retry_count": 0,
            "result": {"rows": 3, "api_token": "do-not-write"},
            "at": datetime(2026, 8, 10, tzinfo=timezone.utc),
        }
    )

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    event = json.loads(lines[0])
    assert event["result"] == {"rows": 3, "api_token": "[REDACTED]"}
    assert event["at"] == "2026-08-10T00:00:00+00:00"


def test_jsonl_tracer_redacts_common_key_styles_and_credentials_but_keeps_token_count(tmp_path):
    """Narrow redaction would leak common credentials; broad token matching hides metrics."""
    path = tmp_path / "trace.jsonl"
    JsonlTracer(path).emit(
        {
            "apiKey": "api-key-value",
            "cookie": "session=abc",
            "credentials": {"username": "agent", "password": "password-value"},
            "token_count": 123,
            "message": "Upstream rejected Bearer abc.def-123",
            "error": "Proxy rejected basic dXNlcjpwYXNz",
        }
    )

    event = json.loads(path.read_text(encoding="utf-8"))
    assert event["apiKey"] == "[REDACTED]"
    assert event["cookie"] == "[REDACTED]"
    assert event["credentials"] == "[REDACTED]"
    assert event["token_count"] == 123
    assert event["message"] == "Upstream rejected Bearer [REDACTED]"
    assert event["error"] == "Proxy rejected basic [REDACTED]"
    assert {"trace_id", "session_id", "call_id", "tool_name", "status", "elapsed_ms", "retry_count", "at"} <= set(event)


def test_jsonl_tracer_minimizes_nested_payloads_containing_credentials(tmp_path):
    """Nested payload values must never survive tracing, even when keys are unknown."""
    path = tmp_path / "trace.jsonl"
    JsonlTracer(path).emit(
        {
            "payload": {
                "headers": {
                    "x-api-key": "api-secret",
                    "proxy-authorization": "Basic cHJveHk6c2VjcmV0",
                },
                "rows": [
                    {"value": "prefix Bearer nested-secret suffix"},
                    "Basic bGlzdDpzZWNyZXQ=",
                ],
            }
        }
    )

    trace_text = path.read_text(encoding="utf-8")
    event = json.loads(trace_text)
    assert event["payload"] == {
        "policy": "minimized",
        "type": "object",
        "field_count": 2,
        "sensitive_field_count": 0,
    }
    assert "secret" not in trace_text.casefold()


def test_jsonl_tracer_minimizes_raw_tool_inputs_without_serializing_pii(tmp_path):
    """Tool input traces must keep shape metadata, never user-supplied record bodies."""
    path = tmp_path / "trace.jsonl"
    JsonlTracer(path).emit(
        {
            "tool_name": "load_records",
            "input": {
                "records": [
                    {
                        "email": "ada@example.com",
                        "ssn": "123-45-6789",
                        "credit_card": "4111 1111 1111 1111",
                        "secret_key": "raw-secret-value",
                    }
                ],
                "batch_id": "batch-privacy",
            },
            "result": {"loaded": 1},
        }
    )

    trace_text = path.read_text(encoding="utf-8")
    event = json.loads(trace_text)
    assert event["input"] == {
        "policy": "minimized",
        "type": "object",
        "field_count": 2,
        "sensitive_field_count": 0,
    }
    assert event["result"] == {"loaded": 1}
    for raw_value in (
        "ada@example.com",
        "123-45-6789",
        "4111 1111 1111 1111",
        "raw-secret-value",
        "secret_key",
    ):
        assert raw_value not in trace_text


def test_jsonl_tracer_minimizes_unknown_nested_values_instead_of_trusting_field_names(tmp_path):
    """Unexpected event fields cannot bypass the input-minimization boundary."""
    path = tmp_path / "trace.jsonl"
    JsonlTracer(path).emit(
        {
            "tool_name": "inspect_schema",
            "client_supplied_context": {
                "contact": "grace@example.com",
                "nested": {"secret_key": "do-not-log"},
            },
        }
    )

    trace_text = path.read_text(encoding="utf-8")
    event = json.loads(trace_text)
    assert event["client_supplied_context"] == {
        "policy": "minimized",
        "type": "object",
        "field_count": 2,
        "sensitive_field_count": 0,
    }
    assert "grace@example.com" not in trace_text
    assert "do-not-log" not in trace_text


class _InterleavingEpochs(dict[str, int]):
    """Makes both racing reads observe the same absent value when no lock exists."""

    def __init__(self) -> None:
        super().__init__()
        self._barrier = Barrier(2)

    def get(self, key: str, default: int = 0) -> int:
        value = super().get(key, default)
        if value == default:
            try:
                self._barrier.wait(timeout=0.1)
            except Exception:
                pass
        return value


class _InterleavingKeys(set[str]):
    """Makes both racing membership tests miss when no lock exists."""

    def __init__(self) -> None:
        super().__init__()
        self._barrier = Barrier(2)

    def __contains__(self, key: object) -> bool:
        present = super().__contains__(key)
        if not present:
            try:
                self._barrier.wait(timeout=0.1)
            except Exception:
                pass
        return present


class _FakeRedis:
    """Small in-memory Redis surface used to test the real adapter offline."""

    def __init__(self) -> None:
        self._epochs: dict[str, int] = {}
        self._hashes: dict[str, dict[str, bytes]] = {}
        self._values: dict[str, str] = {}

    def eval(self, _script, key_count, epoch_key, response_key, response_id):
        assert key_count == 2
        epoch = self._epochs.get(epoch_key, 0) + 1
        self._epochs[epoch_key] = epoch
        self._hashes[response_key] = {
            "response_id": response_id.encode("utf-8"),
            "epoch": str(epoch).encode("utf-8"),
        }
        return epoch

    def hmget(self, key, *fields):
        values = self._hashes.get(key, {})
        return [values.get(field) for field in fields]

    def set(self, key, value, *, nx=False):
        if nx and key in self._values:
            return False
        self._values[key] = value
        return True
