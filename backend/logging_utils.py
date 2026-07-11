from __future__ import annotations

import datetime
import re
from pathlib import Path

_SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def safe_log_token(value: str | None, fallback: str = "") -> str:
    token = _SAFE_TOKEN_RE.sub("-", str(value or "").strip()).strip("-._")
    return (token or fallback)[:80]


def resolve_session_log_dir(
    log_root: Path,
    *,
    session_id: str,
    mode: str,
    analysis_id: str | None = None,
) -> tuple[Path, str]:
    """Return a fresh, participant-identifiable directory per connection."""
    log_root.mkdir(parents=True, exist_ok=True)
    safe_session_id = safe_log_token(session_id, "session")
    safe_analysis_id = safe_log_token(analysis_id)
    safe_mode = safe_log_token(mode, "audio")

    if safe_analysis_id:
        return (
            _new_log_dir(log_root, f"{safe_analysis_id}_{safe_mode}"),
            safe_analysis_id,
        )

    return _new_log_dir(log_root, f"{safe_session_id}_{safe_mode}"), safe_session_id


def _new_log_dir(log_root: Path, suffix: str) -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = log_root / f"{ts}_{suffix}"
    counter = 2
    while log_dir.exists():
        log_dir = log_root / f"{ts}_{suffix}_{counter}"
        counter += 1
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
