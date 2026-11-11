"""008 T2: 预览 API 的只读性、模型解析、blocker 与脱敏。"""

import hashlib
import json
from pathlib import Path

from switch_fixtures import (
    SECRET,
    add_codex_profile,
    add_profile,
    make_switch_harness,
    post_preview,
    preview_json,
    write_claude_settings,
    write_codex_files,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def claude_content() -> bytes:
    return json.dumps(
        {
            "model": "claude-sonnet-4",
            "env": {
                "ANTHROPIC_BASE_URL": "https://old.example.com",
                "ANTHROPIC_API_KEY": "sk-old-api-key",
                "KEEP_ME": "原样保留",
            },
        },
        ensure_ascii=False,
    ).encode()


def test_preview_returns_fields_without_touching_disk(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())
    before = settings.read_bytes()
    profiles_before = (tmp_path / "profiles.json").read_bytes()

    body = preview_json(harness, profile.id)

    assert body["tool_id"] == "claude-code"
    assert body["profile_id"] == profile.id
    assert body["model"] == "claude-sonnet-4"
    assert [item["id"] for item in body["available_models"]] == [
        "claude-sonnet-4",
        "claude-opus-4",
    ]
    assert body["blockers"] == []
    assert body["warnings"] == []
    assert body["can_apply"] is True
    assert body["restart_required"] is True
    assert "重启" in body["restart_message"]
    assert len(body["preview_digest"]) == 64
    assert len(body["observations"]) == 1

    preview_file = body["files"][0]
    assert preview_file["path"] == str(settings.resolve())
    assert preview_file["action"] == "updated"
    assert preview_file["before_sha256"] == sha256(before)
    assert preview_file["before_size"] == len(before)
    assert preview_file["after_sha256"] != preview_file["before_sha256"]
    fields = {change["field"]: change for change in preview_file["changes"]}
    assert fields["env.ANTHROPIC_BASE_URL"]["before"] == "https://old.example.com"
    assert fields["env.ANTHROPIC_BASE_URL"]["after"] == "https://relay.example.com"
    assert "env.ANTHROPIC_API_KEY" in fields

    assert settings.read_bytes() == before
    assert (tmp_path / "profiles.json").read_bytes() == profiles_before
    assert not (tmp_path / "snapshots").exists()
    assert not (tmp_path / "db" / "app.sqlite3").exists()


def test_preview_response_never_contains_plaintext_secret(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    write_claude_settings(harness, claude_content())

    response = post_preview(harness, profile.id)

    assert response.status_code == 200
    assert SECRET not in response.text
    assert "sk-old-api-key" not in response.text
    body = response.json()
    secret_change = next(
        change
        for change in body["files"][0]["changes"]
        if change["field"] == "env.ANTHROPIC_API_KEY"
    )
    assert secret_change["after"] != SECRET


def test_preview_rejects_model_outside_profile_list(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    write_claude_settings(harness, claude_content())

    response = post_preview(harness, profile.id, model="gpt-5")

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "SWITCH_MODEL_UNKNOWN"
    assert "gpt-5" in body["message"]


def test_preview_uses_explicit_model_from_profile(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    write_claude_settings(harness, claude_content())

    body = preview_json(harness, profile.id, model="claude-opus-4")

    assert body["model"] == "claude-opus-4"
    fields = {change["field"]: change for change in body["files"][0]["changes"]}
    assert fields["model"]["after"] == "claude-opus-4"


def test_preview_empty_model_list_keeps_current_model(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness, models=())
    content = json.dumps(
        {
            "env": {
                "ANTHROPIC_BASE_URL": "https://old.example.com",
                "ANTHROPIC_MODEL": "current-model",
            }
        }
    ).encode()
    write_claude_settings(harness, content)

    body = preview_json(harness, profile.id)

    assert body["model"] is None
    assert body["available_models"] == []
    assert [warning["code"] for warning in body["warnings"]] == ["NO_MODELS"]
    assert body["can_apply"] is True
    fields = {change["field"] for change in body["files"][0]["changes"]}
    assert "env.ANTHROPIC_MODEL" not in fields
    assert "model" not in fields


def test_preview_protocol_mismatch_blocks_without_writing(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)

    body = preview_json(harness, profile.id, tool_id="codex-cli")

    assert [blocker["code"] for blocker in body["blockers"]] == ["PROTOCOL_MISMATCH"]
    assert body["files"] == []
    assert body["can_apply"] is False
    assert not (harness.codex_dir / "config.toml").exists()
    assert not (harness.codex_dir / "auth.json").exists()


def test_preview_missing_secret_is_a_blocker(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    write_claude_settings(harness, claude_content())
    harness.keyring.values.clear()

    body = preview_json(harness, profile.id)

    assert [blocker["code"] for blocker in body["blockers"]] == ["SECRET_MISSING"]
    assert body["files"] == []
    assert body["can_apply"] is False


def test_preview_secret_store_error_is_a_blocker(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    write_claude_settings(harness, claude_content())
    harness.keyring.fail_get = True

    body = preview_json(harness, profile.id)

    assert [blocker["code"] for blocker in body["blockers"]] == ["SECRET_STORE_ERROR"]
    assert body["can_apply"] is False


def test_preview_without_secret_keeps_existing_credentials(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness, secret=None)
    write_claude_settings(harness, claude_content())

    body = preview_json(harness, profile.id)

    assert [warning["code"] for warning in body["warnings"]] == ["PROFILE_SECRET_EMPTY"]
    assert body["can_apply"] is True
    fields = {change["field"] for change in body["files"][0]["changes"]}
    assert "env.ANTHROPIC_API_KEY" not in fields
    assert "env.ANTHROPIC_AUTH_TOKEN" not in fields


def test_preview_corrupt_settings_is_a_blocker(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    write_claude_settings(harness, '{"env": ')

    body = preview_json(harness, profile.id)

    assert [blocker["code"] for blocker in body["blockers"]] == ["PARSE_ERROR"]
    assert body["files"] == []
    assert body["can_apply"] is False
    assert "第 1 行" in body["blockers"][0]["message"]


def test_preview_unknown_or_uninstalled_tool_is_not_found(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)

    unknown = post_preview(harness, profile.id, tool_id="unknown-tool")
    assert unknown.status_code == 404
    assert unknown.json()["code"] == "TOOL_NOT_FOUND"

    settings = harness.claude_dir / "settings.json"
    settings.parent.rmdir()
    uninstalled = post_preview(harness, profile.id)
    assert uninstalled.status_code == 404
    assert uninstalled.json()["code"] == "TOOL_NOT_FOUND"


def test_preview_read_only_file_is_a_blocker(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path, access=lambda _path, _mode: False)
    profile = add_profile(harness)
    write_claude_settings(harness, claude_content())

    body = preview_json(harness, profile.id)

    assert [blocker["code"] for blocker in body["blockers"]] == ["FILE_NOT_WRITABLE"]
    assert body["can_apply"] is False


def test_preview_unwritable_directory_is_a_blocker(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path, access=lambda _path, _mode: False)
    profile = add_profile(harness)

    body = preview_json(harness, profile.id)

    assert [blocker["code"] for blocker in body["blockers"]] == ["DIRECTORY_NOT_WRITABLE"]
    assert body["can_apply"] is False
    assert not (harness.claude_dir / "settings.json").exists()


def test_preview_digest_ignores_mtime_only_changes(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)
    settings = write_claude_settings(harness, claude_content())

    first = preview_json(harness, profile.id)
    settings.touch()
    second = preview_json(harness, profile.id)

    assert first["preview_digest"] == second["preview_digest"]


def test_preview_codex_maps_config_and_auth_without_leaking_secret(
    tmp_path: Path,
) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_codex_profile(harness)
    config, auth = write_codex_files(
        harness,
        config=(
            'model = "gpt-old"\n'
            'model_provider = "openai"\n'
            "\n"
            "[model_providers.openai]\n"
            'name = "OpenAI"\n'
            'base_url = "https://old.example.com/v1"\n'
            'wire_api = "chat"\n'
        ),
        auth=json.dumps(
            {
                "OPENAI_API_KEY": "sk-old-openai-key",
                "tokens": {"id_token": "oauth-token"},
            }
        ),
    )
    config_before = config.read_bytes()
    auth_before = auth.read_bytes()

    response = post_preview(harness, profile.id, tool_id="codex-cli")

    assert response.status_code == 200
    assert SECRET not in response.text
    assert "sk-old-openai-key" not in response.text
    body = response.json()
    assert body["can_apply"] is True
    assert [warning["code"] for warning in body["warnings"]] == ["OAUTH_AUTH_PRESENT"]
    assert len(body["files"]) == 2
    assert len(body["observations"]) == 2
    fields = {
        change["field"] for preview_file in body["files"] for change in preview_file["changes"]
    }
    assert "model_providers.openai.base_url" in fields
    assert "OPENAI_API_KEY" in fields
    assert config.read_bytes() == config_before
    assert auth.read_bytes() == auth_before


def test_preview_missing_settings_is_created_action(tmp_path: Path) -> None:
    harness = make_switch_harness(tmp_path)
    profile = add_profile(harness)

    body = preview_json(harness, profile.id)

    assert body["can_apply"] is True
    assert body["files"][0]["action"] == "created"
    assert body["files"][0]["before_sha256"] is None
    assert body["files"][0]["before_size"] == 0
    assert not (harness.claude_dir / "settings.json").exists()
