"""Safe append-only JSONL tracing with bounded input capture.

The tracer deliberately records tool-input *shape*, not tool-input values. It
is a practical minimisation boundary for observability, not a replacement for a
full data-classification or DLP system.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import json
from pathlib import Path
import re
from threading import Lock
from typing import Any
from uuid import uuid4


_SENSITIVE_KEYS = frozenset(
    {
        "apikey",
        "xapikey",
        "apitoken",
        "authorization",
        "proxyauthorization",
        "accesstoken",
        "clientsecret",
        "cookie",
        "credentials",
        "creditcard",
        "cardnumber",
        "idtoken",
        "password",
        "refreshtoken",
        "secret",
        "secretkey",
        "socialsecuritynumber",
        "ssn",
        "token",
    }
)
_INPUT_FIELDS = frozenset(
    {
        "args",
        "arguments",
        "body",
        "headers",
        "input",
        "inputs",
        "parameters",
        "params",
        "payload",
        "query",
        "record",
        "records",
        "request",
        "requestbody",
        "toolargs",
        "toolinput",
    }
)
_CONTRACT_FIELDS = frozenset(
    {
        "at",
        "call_id",
        "elapsed_ms",
        "event",
        "retry_count",
        "session_id",
        "status",
        "tool_name",
        "trace_id",
    }
)
_SAFE_TEXT_FIELDS = frozenset({"error", "message"})
_SAFE_METADATA_FIELDS = frozenset({"metrics", "result", "result_summary"})
_SAFE_NUMERIC_FIELDS = frozenset(
    {
        "cache_hit_count",
        "http_status",
        "input_tokens",
        "output_tokens",
        "record_count",
        "result_rows",
        "result_size",
        "token_count",
    }
)
_CREDENTIAL_FRAGMENT = re.compile(r"\b(?P<scheme>bearer|basic)\s+[^\s,;]+", re.IGNORECASE)
_EMAIL_FRAGMENT = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_SSN_FRAGMENT = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_CARD_FRAGMENT = re.compile(r"\b(?:\d[ -]?){12,18}\d\b")
_ASSIGNMENT_SECRET_FRAGMENT = re.compile(
    r"\b(?P<key>api[_-]?key|secret[_-]?key|password|token)\b\s*[:=]\s*[^\s,;]+",
    re.IGNORECASE,
)
_MAX_TRACE_TEXT_CHARACTERS = 512


class JsonlTracer:
    """Append structured events while minimising untrusted tool-input values."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def emit(self, event: Mapping[str, Any]) -> None:
        safe_event = _safe_event(_with_trace_contract(event))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe_event, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def _with_trace_contract(event: Mapping[str, Any]) -> dict[str, Any]:
    """Supply the stable metadata envelope expected by runtime observability."""
    normalized = dict(event)
    normalized.setdefault("trace_id", str(uuid4()))
    normalized.setdefault("session_id", "anonymous")
    normalized.setdefault("call_id", str(uuid4()))
    normalized.setdefault("tool_name", "runtime")
    normalized.setdefault("status", "completed")
    normalized.setdefault("elapsed_ms", 0)
    normalized.setdefault("retry_count", 0)
    normalized.setdefault("at", datetime.now().astimezone())
    return normalized


def _safe_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Keep contract fields and summaries; minimise every unrecognised value."""
    safe_event: dict[str, Any] = {}
    for raw_key, value in event.items():
        key = str(raw_key)
        normalised_key = _normalise_key(key)
        if _is_sensitive_key(key):
            safe_event[key] = "[REDACTED]"
        elif normalised_key in _INPUT_FIELDS:
            safe_event[key] = _minimise_input(value)
        elif key in _CONTRACT_FIELDS:
            safe_event[key] = _safe_contract_value(value)
        elif key in _SAFE_TEXT_FIELDS:
            safe_event[key] = _safe_text(value)
        elif key in _SAFE_METADATA_FIELDS:
            safe_event[key] = _safe_metadata(value)
        elif key in _SAFE_NUMERIC_FIELDS and isinstance(value, (int, float)):
            safe_event[key] = value
        else:
            safe_event[key] = _minimise_input(value)
    return safe_event


def _safe_contract_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return _redact_sensitive_fragments(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return _minimise_input(value)


def _safe_text(value: Any) -> str:
    if not isinstance(value, str):
        return f"<{type(value).__name__}>"
    redacted = _redact_sensitive_fragments(value)
    if len(redacted) <= _MAX_TRACE_TEXT_CHARACTERS:
        return redacted
    return f"{redacted[:_MAX_TRACE_TEXT_CHARACTERS]}…[TRUNCATED]"


def _safe_metadata(value: Any, *, key: str = "") -> Any:
    """Keep numeric result metrics but never serialize arbitrary output values."""
    if _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {
            str(item_key): _safe_metadata(item_value, key=str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return _minimise_input(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, str):
        return {"type": "string", "length": len(value)}
    return f"<{type(value).__name__}>"


def _minimise_input(value: Any) -> dict[str, Any]:
    """Return structural metadata without retaining supplied values or field names."""
    if isinstance(value, Mapping):
        return {
            "policy": "minimized",
            "type": "object",
            "field_count": len(value),
            "sensitive_field_count": sum(_is_sensitive_key(str(key)) for key in value),
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return {
            "policy": "minimized",
            "type": "array",
            "item_count": len(value),
        }
    if isinstance(value, str):
        return {"policy": "minimized", "type": "string", "length": len(value)}
    if value is None:
        return {"policy": "minimized", "type": "null"}
    if isinstance(value, bool):
        return {"policy": "minimized", "type": "boolean"}
    if isinstance(value, (int, float)):
        return {"policy": "minimized", "type": "number"}
    return {"policy": "minimized", "type": type(value).__name__}


def _normalise_key(key: str) -> str:
    return re.sub(r"[^a-z0-9]", "", key.lower())


def _is_sensitive_key(key: str) -> bool:
    return _normalise_key(key) in _SENSITIVE_KEYS


def _redact_sensitive_fragments(value: str) -> str:
    value = _CREDENTIAL_FRAGMENT.sub(
        lambda match: f"{match.group('scheme')} [REDACTED]", value
    )
    value = _ASSIGNMENT_SECRET_FRAGMENT.sub(
        lambda match: f"{match.group('key')}=[REDACTED]", value
    )
    value = _EMAIL_FRAGMENT.sub("[REDACTED_EMAIL]", value)
    value = _SSN_FRAGMENT.sub("[REDACTED_SSN]", value)
    return _CARD_FRAGMENT.sub("[REDACTED_CARD]", value)
