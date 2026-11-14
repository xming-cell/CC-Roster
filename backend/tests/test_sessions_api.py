"""012 会话回放的适配器与 API 测试。"""

import hashlib
import os
import time
from pathlib import Path

from fastapi.testclient import TestClient
from session_fixtures import seed_claude_session, seed_codex_session

from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.registry import ToolRegistry
from app.api.sessions import get_session_service
from app.main import create_app
from app.services.session_service import SessionService


def make_client(tmp_path: Path) -> TestClient:
    app = create_app()
    registry = ToolRegistry(
        [
            ClaudeCodeAdapter(tmp_path / "claude", which=lambda _name: None),
            CodexCliAdapter(tmp_path / "codex", which=lambda _name: None),
        ]
    )
    app.dependency_overrides[get_session_service] = lambda: SessionService(registry)
    return TestClient(app)


def tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(root).as_posix().encode())
            digest.update(path.read_bytes())
    return digest.hexdigest()


def test_list_sessions_merges_tools_and_keeps_original_read_only(tmp_path: Path) -> None:
    seed_claude_session(tmp_path / "claude")
    seed_codex_session(tmp_path / "codex")
    before = tree_hash(tmp_path)

    response = make_client(tmp_path).get("/api/sessions")

    assert response.status_code == 200
    body = response.json()
    assert {item["tool_id"] for item in body["sessions"]} == {"claude-code", "codex-cli"}
    assert body["sessions"][0]["tool_id"] == "codex-cli"
    assert body["sessions"][0]["title"] == "写一个脚本"
    assert body["sessions"][1]["project_path"] == "/work/alpha"
    assert body["has_more"] is False
    assert tree_hash(tmp_path) == before


def test_list_sessions_supports_tool_filter_and_offset_cursor(tmp_path: Path) -> None:
    for index in range(3):
        path = seed_claude_session(
            tmp_path / "claude",
            session_id=f"session-{index}",
            title=f"title-{index}",
            started_at=f"2026-11-1{index}T09:00:00Z",
        )
        os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))

    client = make_client(tmp_path)
    first = client.get("/api/sessions", params={"tool_id": "claude-code", "limit": 2})
    second = client.get(
        "/api/sessions",
        params={"tool_id": "claude-code", "limit": 2, "cursor": first.json()["next_cursor"]},
    )

    assert [item["title"] for item in first.json()["sessions"]] == ["title-2", "title-1"]
    assert first.json()["has_more"] is True
    assert [item["title"] for item in second.json()["sessions"]] == ["title-0"]
    assert second.json()["has_more"] is False


def test_read_session_preserves_order_and_degrades_unknown_events(tmp_path: Path) -> None:
    seed_codex_session(tmp_path / "codex")

    response = make_client(tmp_path).get("/api/sessions/codex-cli/rollout-2026-11-12T10-00-00-abc")

    assert response.status_code == 200
    body = response.json()
    roles = [message["role"] for message in body["messages"]]
    assert roles == ["user", "assistant", "tool_call", "tool_result", "unknown"]
    assert body["messages"][0]["content"] == "写一个脚本"
    assert body["messages"][2]["tool_name"] == "shell"
    assert body["messages"][4]["content"] == "[未识别事件] mystery_event"


def test_read_session_paginates_without_duplicates(tmp_path: Path) -> None:
    seed_claude_session(tmp_path / "claude")
    client = make_client(tmp_path)

    first = client.get(
        "/api/sessions/claude-code/claude-session-1",
        params={"limit": 2},
    )
    second = client.get(
        "/api/sessions/claude-code/claude-session-1",
        params={"limit": 2, "cursor": first.json()["next_cursor"]},
    )

    assert [item["role"] for item in first.json()["messages"]] == ["user", "assistant"]
    assert first.json()["has_more"] is True
    assert [item["role"] for item in second.json()["messages"]] == ["tool_call", "tool_result"]
    assert second.json()["has_more"] is False


def test_broken_line_reports_warning_without_breaking_other_messages(tmp_path: Path) -> None:
    path = seed_claude_session(tmp_path / "claude")
    path.write_text(
        path.read_text(encoding="utf-8") + "{not-json}\n",
        encoding="utf-8",
    )

    response = make_client(tmp_path).get("/api/sessions/claude-code/claude-session-1")

    assert response.status_code == 200
    assert response.json()["warnings"][0]["code"] == "PARSE_ERROR"
    assert len(response.json()["messages"]) == 4


def test_unknown_tool_and_session_return_error_envelope(tmp_path: Path) -> None:
    client = make_client(tmp_path)

    unknown_tool = client.get("/api/sessions/not-a-tool/whatever")
    unknown_session = client.get("/api/sessions/claude-code/missing")

    assert unknown_tool.status_code == 404
    assert unknown_tool.json()["code"] == "TOOL_NOT_FOUND"
    assert unknown_session.status_code == 404
    assert unknown_session.json()["code"] == "SESSION_NOT_FOUND"


def test_hundreds_of_sessions_list_quickly(tmp_path: Path) -> None:
    for index in range(150):
        path = seed_claude_session(
            tmp_path / "claude",
            session_id=f"bulk-{index}",
            title=f"bulk title {index}",
            started_at="2026-11-12T09:00:00Z",
        )
        os.utime(path, (1_700_000_000 + index, 1_700_000_000 + index))

    started = time.perf_counter()
    response = make_client(tmp_path).get("/api/sessions", params={"limit": 20})
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert len(response.json()["sessions"]) == 20
    assert response.json()["has_more"] is True
    assert elapsed < 2.0


def test_large_session_reads_first_page_quickly(tmp_path: Path) -> None:
    path = seed_codex_session(tmp_path / "codex")
    with path.open("a", encoding="utf-8") as handle:
        for index in range(20_000):
            handle.write(
                '{"type":"response_item","timestamp":"2026-11-12T10:00:06Z",'
                '"payload":{"type":"message","role":"assistant",'
                '"content":[{"type":"output_text","text":"line ' + str(index) + '"}]}}\n'
            )

    started = time.perf_counter()
    response = make_client(tmp_path).get(
        "/api/sessions/codex-cli/rollout-2026-11-12T10-00-00-abc",
        params={"limit": 20},
    )
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert len(response.json()["messages"]) == 20
    assert response.json()["has_more"] is True
    assert elapsed < 2.0
