from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = BACKEND_DIR.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main


def test_health_reports_safe_missing_qwen_configuration(monkeypatch) -> None:
    monkeypatch.setattr(main, "QWEN_API_KEY", "")

    payload = asyncio.run(main.health_check())

    assert payload["status"] == "ok"
    assert payload["qwen_configured"] is False
    assert "DASHSCOPE_API_KEY" in str(payload["qwen_configuration_error"])


def test_public_release_documents_separate_the_olist_data_license() -> None:
    """The tracked Olist snapshot needs an explicit third-party reuse boundary."""
    dataset_contract = (REPOSITORY_ROOT / "docs" / "DATASET.md").read_text(
        encoding="utf-8"
    )
    readme = (REPOSITORY_ROOT / "README.md").read_text(encoding="utf-8")
    software_license = (REPOSITORY_ROOT / "LICENSE").read_text(encoding="utf-8")
    notices_path = REPOSITORY_ROOT / "THIRD_PARTY_NOTICES.md"
    manifest_path = REPOSITORY_ROOT / "docs" / "olist-data-sha256.txt"

    assert notices_path.is_file()
    assert manifest_path.is_file()

    notices = notices_path.read_text(encoding="utf-8")
    manifest = manifest_path.read_text(encoding="utf-8")
    for text in (dataset_contract, notices):
        assert "Brazilian E-Commerce Public Dataset by Olist" in text
        assert "Francisco Magioli" in text
        assert "CC BY-NC-SA 4.0" in text
        assert "https://creativecommons.org/licenses/by-nc-sa/4.0/" in text
        assert "commercial" in text.lower()
        assert "backend/data/olist/" in text

    assert "third-party Olist data" in software_license
    assert "not covered" in software_license
    assert "will be added by a later task" not in readme
    assert "scripts/verify_verbalvis_release.ps1" in readme

    records = [
        line for line in manifest.splitlines() if line and not line.startswith("#")
    ]
    assert len(records) == 9
    assert all(line.startswith("backend/data/olist/") for line in records)
    assert all(
        "  " in line and len(line.rsplit("  ", maxsplit=1)[-1]) == 64
        for line in records
    )


def test_missing_provider_configuration_serves_a_safe_terminal_websocket_state(
    monkeypatch,
) -> None:
    """A no-key session keeps the dashboard visible without exposing a secret."""

    class DisconnectingWebSocket:
        def __init__(self) -> None:
            self.sent: list[dict] = []

        async def send_json(self, payload: dict) -> None:
            self.sent.append(payload)

        async def receive_text(self) -> str:
            raise main.WebSocketDisconnect()

    monkeypatch.setattr(main, "init_views", lambda: None)
    monkeypatch.setattr(main, "realtime_state", lambda: {"dashboard_revision": 7})
    monkeypatch.setattr(main, "get_views_for_frontend", lambda: [{"id": "view-1"}])
    websocket = DisconnectingWebSocket()

    asyncio.run(
        main._serve_configuration_error(
            websocket,
            session_id="session-safe",
            analysis_id=None,
            message="Qwen Realtime is not configured: set DASHSCOPE_API_KEY.",
        )
    )

    assert [payload["type"] for payload in websocket.sent] == [
        "init",
        "configuration_error",
        "runtime_state",
    ]
    assert websocket.sent[0]["views"] == [{"id": "view-1"}]
    assert websocket.sent[0]["dashboard_revision"] == 7
    assert websocket.sent[1]["required"] == ["DASHSCOPE_API_KEY"]
    assert websocket.sent[2] == {
        "type": "runtime_state",
        "phase": "configuration_error",
        "tool_running": False,
        "tools": [],
    }
    assert "sk-" not in json.dumps(websocket.sent)
