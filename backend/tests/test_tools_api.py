"""只读工具 API: T6 的集成测试。

全部通过 TestClient 走真实路由; 依赖注入替换成固定适配器, 不依赖本机 PATH。
覆盖正常 / 空列表 / 部分失败 / 未知 ID / 未安装 / 连续调用与只读性。
"""

import os
from datetime import datetime
from pathlib import Path

from adapter_contract import snapshot_tree
from fastapi.testclient import TestClient
from tool_fixtures import (
    CLAUDE_TOKEN,
    CODEX_KEY,
    StubAdapter,
    claude_adapter,
    codex_adapter,
    seed_claude,
    seed_codex,
)

from app.adapters.base import ToolAdapter
from app.adapters.registry import ToolRegistry
from app.api.tools import get_tool_service
from app.main import create_app
from app.services.tool_discovery import ToolDiscoveryService


def make_client(*adapters: ToolAdapter) -> TestClient:
    """每个测试独立 app + 依赖覆盖, 避免 override 泄漏到其他用例。"""
    app = create_app()
    service = ToolDiscoveryService(ToolRegistry(adapters))
    app.dependency_overrides[get_tool_service] = lambda: service
    return TestClient(app)


def test_list_tools_returns_views_and_timezone_aware_timestamps(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    claude_path = seed_claude(claude_dir)
    timestamp = 1_700_000_000
    os.utime(claude_path, (timestamp, timestamp))
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)

    resp = make_client(claude_adapter(claude_dir), codex_adapter(codex_dir)).get("/api/tools")

    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"tools", "warnings"}
    assert [tool["id"] for tool in body["tools"]] == ["claude-code", "codex-cli"]
    assert [tool["status"] for tool in body["tools"]] == ["ok", "ok"]
    assert body["warnings"] == []

    claude = body["tools"][0]
    assert claude["display_name"] == "Claude Code"
    assert claude["installed"] is True
    assert claude["configured"] is True
    assert claude["version"] is None
    assert claude["provider"] == "Anthropic"
    assert claude["base_url"] == "https://api.anthropic.com"
    assert claude["model"] == "claude-sonnet-4"
    assert claude["is_third_party"] is False
    assert claude["config_path"] == str(claude_path)
    assert claude["has_secret"] is True
    assert claude["secret_preview"] == "sk-a****cdef"
    assert claude["warnings"] == []
    assert claude["capabilities"] == {
        "read": True,
        "write": True,
        "sessions": False,
        "launch": False,
        "write_mode": "managed_fields",
    }

    modified = datetime.fromisoformat(claude["last_modified"].replace("Z", "+00:00"))
    assert modified.utcoffset() is not None
    assert int(modified.timestamp()) == timestamp
    assert CLAUDE_TOKEN not in resp.text
    assert CODEX_KEY not in resp.text


def test_list_tools_returns_empty_list_when_nothing_installed(tmp_path: Path) -> None:
    client = make_client(
        claude_adapter(tmp_path / "no-claude"),
        codex_adapter(tmp_path / "no-codex"),
    )

    resp = client.get("/api/tools")

    assert resp.status_code == 200
    assert resp.json() == {"tools": [], "warnings": []}


def test_partial_failure_keeps_healthy_tool_and_reports_warning(tmp_path: Path) -> None:
    secret = "sk-broken-1234567890abcdef"
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        '{"env": {"ANTHROPIC_AUTH_TOKEN": "' + secret + '"}',
        encoding="utf-8",
    )
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)

    resp = make_client(claude_adapter(claude_dir), codex_adapter(codex_dir)).get("/api/tools")

    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert [tool["status"] for tool in tools] == ["error", "ok"]
    assert tools[0]["warnings"][0]["code"] == "PARSE_ERROR"
    assert "第 1 行第" in tools[0]["warnings"][0]["message"]
    assert tools[1]["model"] == "gpt-5-codex"
    assert secret not in resp.text
    assert "Traceback" not in resp.text


def test_get_tool_returns_single_view(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)

    resp = make_client(claude_adapter(claude_dir)).get("/api/tools/claude-code")

    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == "claude-code"
    assert body["display_name"] == "Claude Code"
    assert body["model"] == "claude-sonnet-4"
    assert CLAUDE_TOKEN not in resp.text


def test_unknown_tool_id_returns_404_envelope(tmp_path: Path) -> None:
    resp = make_client(claude_adapter(tmp_path / "claude")).get("/api/tools/not-a-tool")

    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "TOOL_NOT_FOUND"
    assert isinstance(body["message"], str)
    assert "Traceback" not in resp.text


def test_uninstalled_tool_detail_returns_404(tmp_path: Path) -> None:
    resp = make_client(claude_adapter(tmp_path / "missing")).get("/api/tools/claude-code")

    assert resp.status_code == 404
    assert resp.json()["code"] == "TOOL_NOT_FOUND"


def test_list_tools_accepts_combined_text_and_status_filters(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)

    resp = make_client(claude_adapter(claude_dir), codex_adapter(codex_dir)).get(
        "/api/tools",
        params={
            "name": "  CLAUDE  ",
            "provider": "anthropic",
            "model": "SONNET",
            "status": "ok",
        },
    )

    assert resp.status_code == 200
    assert [tool["id"] for tool in resp.json()["tools"]] == ["claude-code"]


def test_list_tools_rejects_invalid_status_filter(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)

    resp = make_client(claude_adapter(claude_dir)).get("/api/tools", params={"status": "unknown"})

    assert resp.status_code == 422


def test_adapter_failure_is_isolated_into_top_level_warning(tmp_path: Path) -> None:
    secret = "sk-exploding-1234567890abcdef"
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)
    exploding = StubAdapter("exploding-tool", error=RuntimeError(f"boom {secret}"))

    resp = make_client(exploding, codex_adapter(codex_dir)).get("/api/tools")

    assert resp.status_code == 200
    body = resp.json()
    assert [tool["id"] for tool in body["tools"]] == ["codex-cli"]
    assert body["warnings"][0]["code"] == "ADAPTER_ERROR"
    assert "exploding-tool" in body["warnings"][0]["message"]
    assert secret not in resp.text


def test_get_tool_adapter_failure_returns_500_without_traceback(tmp_path: Path) -> None:
    secret = "sk-exploding-1234567890abcdef"
    exploding = StubAdapter("exploding-tool", error=RuntimeError(f"boom {secret}"))

    resp = make_client(exploding).get("/api/tools/exploding-tool")

    assert resp.status_code == 500
    body = resp.json()
    assert body["code"] == "ADAPTER_ERROR"
    assert secret not in resp.text
    assert "Traceback" not in resp.text


def test_consecutive_calls_are_idempotent_and_never_touch_files(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)
    before = (snapshot_tree(claude_dir), snapshot_tree(codex_dir))
    client = make_client(claude_adapter(claude_dir), codex_adapter(codex_dir))

    first_list = client.get("/api/tools")
    second_list = client.get("/api/tools")
    first_detail = client.get("/api/tools/claude-code")
    second_detail = client.get("/api/tools/codex-cli")

    assert first_list.json() == second_list.json()
    assert first_detail.status_code == 200
    assert second_detail.status_code == 200
    assert (snapshot_tree(claude_dir), snapshot_tree(codex_dir)) == before
    assert (client.get("/api/tools/claude-code").json()) == first_detail.json()
