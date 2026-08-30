from __future__ import annotations

import asyncio
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main


def test_health_reports_safe_missing_qwen_configuration(monkeypatch) -> None:
    monkeypatch.setattr(main, "QWEN_API_KEY", "")

    payload = asyncio.run(main.health_check())

    assert payload["status"] == "ok"
    assert payload["qwen_configured"] is False
    assert "DASHSCOPE_API_KEY" in str(payload["qwen_configuration_error"])
