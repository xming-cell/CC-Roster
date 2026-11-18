"""016 全链路密钥泄露扫描: 响应 / 审计 / 快照 / 日志 / 对话存储。"""

from pathlib import Path

import pytest
from switch_fixtures import (
    add_profile,
    apply_payload,
    make_switch_harness,
    preview_json,
    write_claude_settings,
)


def test_secret_never_appears_in_responses_audit_snapshots_or_logs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    harness = make_switch_harness(tmp_path / "data")
    profile = add_profile(harness)
    write_claude_settings(harness, '{"model":"claude-sonnet-4","env":{}}')
    preview = preview_json(harness, profile.id)

    applied = harness.client.post("/api/switch/apply", json=apply_payload(preview))
    assert applied.status_code == 200, applied.text
    audit = harness.client.get("/api/audit")
    snapshots = harness.client.get("/api/snapshots")
    snapshot_id = applied.json()["snapshot_id"]
    detail = harness.client.get(f"/api/snapshots/{snapshot_id}")

    responses = [applied.text, audit.text, snapshots.text, detail.text]
    assert all("sk-switch-secret" not in text for text in responses)
    assert "sk-switch-secret" not in caplog.text

    for root_name in ("snapshots", "db", "profiles.json", "chat_sessions.json"):
        target = harness.data_dir / root_name
        if not target.exists():
            continue
        files = (
            [target] if target.is_file() else [path for path in target.rglob("*") if path.is_file()]
        )
        for path in files:
            assert b"sk-switch-secret" not in path.read_bytes(), path


def test_secret_is_redacted_in_error_messages(harness_with_secret_response) -> None:
    response = harness_with_secret_response
    assert "sk-ant-" not in response.text
    assert "****" in response.text


@pytest.fixture
def harness_with_secret_response(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    harness = make_switch_harness(tmp_path / "data")
    profile = add_profile(harness, secret="sk-ant-error-secret-123456")
    # 预览把密钥写入 diff 时只展示脱敏值
    write_claude_settings(harness, '{"model":"claude-sonnet-4"}')
    return harness.client.post(
        "/api/switch/preview",
        json={"tool_id": "claude-code", "profile_id": profile.id},
    )
