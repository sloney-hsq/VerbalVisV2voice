from __future__ import annotations

import datetime
import re
import threading
from pathlib import Path

_SAFE_TOKEN_RE = re.compile(r"[^A-Za-z0-9_.-]+")
_LOG_DIR_LOCK = threading.Lock()
_ANALYSIS_LOG_DIRS: dict[tuple[str, str, str], Path] = {}


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
    """Return the log directory and stable log scope id for this connection."""
    log_root.mkdir(parents=True, exist_ok=True)
    safe_session_id = safe_log_token(session_id, "session")
    safe_analysis_id = safe_log_token(analysis_id)
    safe_mode = safe_log_token(mode, "session")

    if safe_analysis_id:
        suffix = f"{safe_analysis_id}_{safe_mode}"
        key = (str(log_root.resolve()), safe_analysis_id, safe_mode)
        with _LOG_DIR_LOCK:
            cached = _ANALYSIS_LOG_DIRS.get(key)
            if cached and cached.exists():
                return cached, safe_analysis_id

            matches = sorted(
                (path for path in log_root.glob(f"*_{suffix}") if path.is_dir()),
                key=lambda path: path.stat().st_mtime,
                reverse=True,
            )
            log_dir = matches[0] if matches else _new_log_dir(log_root, suffix)
            _ANALYSIS_LOG_DIRS[key] = log_dir
            return log_dir, safe_analysis_id

    return _new_log_dir(log_root, f"{safe_session_id}_{safe_mode}"), safe_session_id


def _new_log_dir(log_root: Path, suffix: str) -> Path:
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = log_root / f"{ts}_{suffix}"
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir
