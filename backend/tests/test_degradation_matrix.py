"""016 降级矩阵: 不认识 / 版本超预期 / 解析失败 / 外部改动都不写盘。"""

import hashlib
from pathlib import Path

from fastapi.testclient import TestClient
from switch_fixtures import add_profile, make_switch_harness, preview_json, write_claude_settings
from tool_fixtures import claude_adapter

from app.adapters.registry import ToolRegistry
from app.api.tools import get_tool_service
from app.main import create_app
from app.services.tool_discovery import ToolDiscoveryService


def tool_client(config_dir: Path) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_tool_service] = lambda: ToolDiscoveryService(
        ToolRegistry([claude_adapter(config_dir)])
    )
    return TestClient(app)


def test_unknown_json_shape_degrades_to_warning(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text("[]", encoding="utf-8")

    response = tool_client(config_dir).get("/api/tools")

    tool = response.json()["tools"][0]
    assert tool["status"] == "error"
    assert tool["warnings"][0]["code"] == "UNKNOWN_FORMAT"


def test_unsupported_schema_version_degrades_to_warning(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text('{"schema_version": 99}', encoding="utf-8")

    response = tool_client(config_dir).get("/api/tools")

    tool = response.json()["tools"][0]
    assert tool["status"] == "error"
    assert tool["warnings"][0]["code"] == "UNSUPPORTED_VERSION"


def test_broken_config_blocks_preview_without_changing_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    harness = make_switch_harness(tmp_path / "data")
    profile = add_profile(harness)
    path = write_claude_settings(harness, "{broken")
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    response = harness.client.post(
        "/api/switch/preview",
        json={"tool_id": "claude-code", "profile_id": profile.id},
    )

    assert response.status_code == 200
    assert response.json()["can_apply"] is False
    assert response.json()["blockers"][0]["code"] == "PARSE_ERROR"
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_external_change_is_rejected_and_file_preserved(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    harness = make_switch_harness(tmp_path / "data")
    profile = add_profile(harness)
    path = write_claude_settings(harness, '{"model":"claude-sonnet-4"}')
    preview = preview_json(harness, profile.id)
    path.write_text('{"model":"changed-outside"}', encoding="utf-8")
    after_change = path.read_bytes()

    response = harness.client.post(
        "/api/switch/apply",
        json={
            "tool_id": "claude-code",
            "profile_id": profile.id,
            "preview_digest": preview["preview_digest"],
            "observations": preview["observations"],
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "WRITE_CONFLICT"
    assert path.read_bytes() == after_change
