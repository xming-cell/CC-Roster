"""008 T4: blocker 的可读错误与 apply 零写、无自动合并。"""

import json
from pathlib import Path

from switch_fixtures import (
    SECRET,
    add_profile,
    apply_payload,
    make_switch_harness,
    preview_json,
    write_claude_settings,
)


def claude_content() -> bytes:
    return json.dumps(
        {
            "model": "claude-sonnet-4",
            "env": {
                "ANTHROPIC_BASE_URL": "https://old.example.com",
                "ANTHROPIC_API_KEY": "sk-old-api-key",
                "KEEP_ME": "原样保留",
            },
            "hooks": {"Stop": [{"command": "echo hi"}]},
        },
        ensure_ascii=False,
    ).encode()


def test_read_only_file_blocks_apply_without_writing(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path, access=lambda _path, _mode: False)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    original = settings.read_bytes()
    preview = preview_json(harness, profile.id)

    assert [blocker["code"] for blocker in preview["blockers"]] == ["FILE_NOT_WRITABLE"]
    assert preview["can_apply"] is False
    assert preview["files"] == []

    response = harness.client.post("/api/switch/apply", json=apply_payload(preview))

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "SWITCH_BLOCKED"
    assert "不可写" in body["message"]
    assert "details" not in body
    assert settings.read_bytes() == original
    assert not (tmp_path / "snapshots").exists()


def test_unwritable_directory_blocks_apply_without_creating_file(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path, access=lambda _path, _mode: False)
    profile = add_profile(harness)
    preview = preview_json(harness, profile.id)

    assert [blocker["code"] for blocker in preview["blockers"]] == ["DIRECTORY_NOT_WRITABLE"]
    assert preview["can_apply"] is False

    response = harness.client.post("/api/switch/apply", json=apply_payload(preview))

    assert response.status_code == 409
    assert response.json()["code"] == "SWITCH_BLOCKED"
    assert list(harness.claude_dir.iterdir()) == []
    assert not (tmp_path / "snapshots").exists()


def test_corrupt_config_blocks_apply_and_keeps_bytes(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    broken = '{"env": '
    settings = write_claude_settings(harness, broken)
    preview = preview_json(harness, profile.id)

    assert [blocker["code"] for blocker in preview["blockers"]] == ["PARSE_ERROR"]
    assert "第 1 行" in preview["blockers"][0]["message"]
    assert preview["can_apply"] is False

    response = harness.client.post("/api/switch/apply", json=apply_payload(preview))

    assert response.status_code == 409
    assert response.json()["code"] == "SWITCH_BLOCKED"
    assert settings.read_text(encoding="utf-8") == broken
    assert not (tmp_path / "snapshots").exists()


def test_external_edit_is_never_auto_merged(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    preview = preview_json(harness, profile.id)
    external = json.dumps(
        {
            "env": {
                "ANTHROPIC_BASE_URL": "https://external.example.com",
                "ANTHROPIC_API_KEY": "sk-external-key",
                "KEEP_ME": "外部改过",
            },
            "external_added": {"by": "user"},
        },
        ensure_ascii=False,
    ).encode()
    settings.write_bytes(external)

    response = harness.client.post("/api/switch/apply", json=apply_payload(preview))

    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "WRITE_CONFLICT"
    assert body["details"]["conflicts"][0]["reason"] == "CONTENT_CHANGED"
    assert settings.read_bytes() == external
    assert SECRET.encode() not in settings.read_bytes()
    assert not (tmp_path / "snapshots").exists()
