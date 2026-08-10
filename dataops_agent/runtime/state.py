"""State-store contracts and in-memory/Redis implementations."""

from __future__ import annotations

from collections.abc import Callable
from threading import Lock
from typing import Any, Protocol


class StateStore(Protocol):
    """Coordinates response ownership and idempotent mutating operations."""

    def claim_response(self, session_id: str, response_id: str) -> int:
        """Make a response current for its session and return its new epoch."""

    def admit_tool(self, session_id: str, response_id: str, epoch: int) -> bool:
        """Return whether the response still owns execution for this session."""

    def claim_idempotency(self, key: str) -> bool:
        """Atomically claim a mutation key, returning False for duplicates."""


class InMemoryStateStore:
    """A deterministic state-store implementation for local runs and tests."""

    def __init__(self) -> None:
        self._epochs: dict[str, int] = {}
        self._responses: dict[str, tuple[str, int]] = {}
        self._idempotency_keys: set[str] = set()
        self._lock = Lock()

    def claim_response(self, session_id: str, response_id: str) -> int:
        with self._lock:
            epoch = self._epochs.get(session_id, 0) + 1
            self._epochs[session_id] = epoch
            self._responses[session_id] = (response_id, epoch)
            return epoch

    def admit_tool(self, session_id: str, response_id: str, epoch: int) -> bool:
        with self._lock:
            return self._responses.get(session_id) == (response_id, epoch)

    def claim_idempotency(self, key: str) -> bool:
        with self._lock:
            if key in self._idempotency_keys:
                return False
            self._idempotency_keys.add(key)
            return True


_CLAIM_RESPONSE_LUA = """
local epoch = redis.call('INCR', KEYS[1])
redis.call('HSET', KEYS[2], 'response_id', ARGV[1], 'epoch', epoch)
return epoch
"""


class RedisStateStore:
    """A lazy Redis adapter; a client or client factory is injected by callers."""

    def __init__(
        self,
        client: Any | None = None,
        *,
        client_factory: Callable[[], Any] | None = None,
        key_prefix: str = "dataops:runtime",
    ) -> None:
        if client is not None and client_factory is not None:
            raise ValueError("provide either client or client_factory, not both")
        self._client = client
        self._client_factory = client_factory
        self._key_prefix = key_prefix.rstrip(":")

    def _redis(self) -> Any:
        if self._client is None:
            if self._client_factory is not None:
                self._client = self._client_factory()
            else:
                try:
                    import redis
                except ImportError as error:
                    raise RuntimeError("RedisStateStore requires redis-py or an injected client") from error
                self._client = redis.Redis()
        return self._client

    def _key(self, *parts: str) -> str:
        return ":".join((self._key_prefix, *parts))

    def claim_response(self, session_id: str, response_id: str) -> int:
        result = self._redis().eval(
            _CLAIM_RESPONSE_LUA,
            2,
            self._key("session", session_id, "epoch"),
            self._key("session", session_id, "response"),
            response_id,
        )
        return int(result)

    def admit_tool(self, session_id: str, response_id: str, epoch: int) -> bool:
        current_response, current_epoch = self._redis().hmget(
            self._key("session", session_id, "response"),
            "response_id",
            "epoch",
        )
        return _text(current_response) == response_id and _text(current_epoch) == str(epoch)

    def claim_idempotency(self, key: str) -> bool:
        return bool(self._redis().set(self._key("idempotency", key), "1", nx=True))


def _text(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)
