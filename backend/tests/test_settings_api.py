"""016 只读开关测试。"""

import json
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app


def client_for(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    return TestClient(create_app())


def settings_path(tmp_path: Path) -> Path:
    return tmp_path / "CC-Roster" / "settings.json"


def test_toggle_read_only_blocks_config_writes_and_keeps_reads(tmp_path: Path, monkeypatch) -> None:
    client = client_for(tmp_path, monkeypatch)

    initial = client.get("/api/settings")
    enabled = client.put("/api/settings", json={"read_only": True})
    blocked = client.post(
        "/api/profiles",
        json={"name": "x", "protocol": "anthropic", "base_url": "https://a.example", "models": []},
    )
    preview = client.post(
        "/api/switch/preview",
        json={"tool_id": "claude-code", "profile_id": "missing"},
    )
    health = client.post(
        "/api/profiles/00000000-0000-4000-8000-000000000000/health-check",
        json={},
    )
    chat = client.post(
        "/api/chat/sessions",
        json={"tool_id": "claude-code", "profile_id": "x", "project_dir": str(tmp_path)},
    )

    assert initial.status_code == 200
    assert initial.json()["read_only"] is False
    assert enabled.json()["read_only"] is True
    assert "只读" in enabled.json()["message"]
    assert blocked.status_code == 403
    assert blocked.json()["code"] == "READ_ONLY_MODE"
    assert preview.status_code != 403
    assert health.status_code != 403
    assert chat.status_code != 403


def test_disabling_read_only_restores_writes(tmp_path: Path, monkeypatch) -> None:
    client = client_for(tmp_path, monkeypatch)
    client.put("/api/settings", json={"read_only": True})

    disabled = client.put("/api/settings", json={"read_only": False})
    created = client.post(
        "/api/profiles",
        json={
            "name": "恢复可写",
            "protocol": "anthropic",
            "base_url": "https://a.example",
            "models": [{"id": "m"}],
        },
    )

    assert disabled.json()["read_only"] is False
    assert created.status_code == 201


def test_corrupt_settings_fail_closed(tmp_path: Path, monkeypatch) -> None:
    client = client_for(tmp_path, monkeypatch)
    path = settings_path(tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")

    blocked = client.post("/api/profiles", json={})
    read = client.get("/api/settings")

    assert blocked.status_code == 500
    assert blocked.json()["code"] == "SETTINGS_UNREADABLE"
    assert read.status_code == 500


def test_settings_file_is_atomic_and_readable(tmp_path: Path, monkeypatch) -> None:
    client = client_for(tmp_path, monkeypatch)
    client.put("/api/settings", json={"read_only": True})

    raw = json.loads(settings_path(tmp_path).read_text(encoding="utf-8"))

    assert raw["schema_version"] == 1
    assert raw["read_only"] is True
    updated = datetime.fromisoformat(raw["updated_at"].replace("Z", "+00:00"))
    assert updated.utcoffset() is not None
