"""Safe append-only JSONL tracing."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date, datetime
import json
from pathlib import Path
import re
from threading import Lock
from typing import Any


_SENSITIVE_KEYS = frozenset(
    {
        "apikey",
        "apitoken",
        "authorization",
        "accesstoken",
        "clientsecret",
        "cookie",
        "credentials",
        "idtoken",
        "password",
        "refreshtoken",
        "secret",
        "token",
    }
)
_CREDENTIAL_FRAGMENT = re.compile(r"\b(?P<scheme>bearer|basic)\s+[^\s,;]+", re.IGNORECASE)


class JsonlTracer:
    """Append structured events without allowing secrets or exotic objects to break output."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = Lock()

    def emit(self, event: Mapping[str, Any]) -> None:
        safe_event = _safe_value(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(safe_event, ensure_ascii=False, separators=(",", ":")))
            handle.write("\n")


def _safe_value(value: Any, *, key: str = "") -> Any:
    if _is_sensitive_key(key):
        return "[REDACTED]"
    if isinstance(value, Mapping):
        return {str(item_key): _safe_value(item_value, key=str(item_key)) for item_key, item_value in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, str):
        return _redact_credential_fragment(value) if key.lower() in {"message", "error"} else value
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return f"<{type(value).__name__}>"


def _is_sensitive_key(key: str) -> bool:
    normalized = re.sub(r"[^a-z0-9]", "", key.lower())
    return normalized in _SENSITIVE_KEYS


def _redact_credential_fragment(value: str) -> str:
    return _CREDENTIAL_FRAGMENT.sub(lambda match: f"{match.group('scheme')} [REDACTED]", value)
