"""本机配置导入: 四类工具映射、绑定来源工具与密钥边界。"""

import json
from pathlib import Path

from profile_fixtures import make_profile_harness

SECRET = "sk-ant-" + "l" * 24


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def local_preview(harness, tool_id: str):
    return harness.client.post(f"/api/profiles/import/local/{tool_id}/preview")


def local_import(harness, tool_id: str, policy: str = "skip"):
    return harness.client.post(f"/api/profiles/import/local/{tool_id}", json={"policy": policy})


def assert_bound_inactive(harness, tool_id: str, profile_id: str) -> None:
    body = harness.client.get(f"/api/profiles?tool_id={tool_id}").json()
    assert [profile["id"] for profile in body["profiles"]] == [profile_id]
    assert body["bindings"] == [
        {
            "tool_id": tool_id,
            "profile_id": profile_id,
            "bound_at": body["bindings"][0]["bound_at"],
            "active": False,
            "applied_at": None,
            "snapshot_id": None,
        }
    ]


def test_claude_local_config_maps_fields_secret_and_binding(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "claude"
    write_json(
        config_dir / "settings.json",
        {
            "env": {
                "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
                "ANTHROPIC_AUTH_TOKEN": SECRET,
                "ANTHROPIC_MODEL": "claude-opus-4-5",
            }
        },
    )
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(config_dir))
    harness = make_profile_harness(tmp_path / "app")

    preview_response = local_preview(harness, "claude-code")
    assert preview_response.status_code == 200, preview_response.text
    preview = preview_response.json()
    assert preview["source"] == "local_config"
    assert preview["tool_id"] == "claude-code"
    assert preview["source_path"].endswith("settings.json")
    assert preview["items"][0]["has_secret"] is True
    assert SECRET not in preview_response.text

    result = local_import(harness, "claude-code")
    assert result.status_code == 201, result.text
    profile = harness.client.get("/api/profiles/" + result.json()["profile_ids"][0]).json()
    assert profile["name"] == "Anthropic 本机配置"
    assert profile["protocol"] == "anthropic"
    assert profile["base_url"] == "https://api.anthropic.com"
    assert [model["id"] for model in profile["models"]] == ["claude-opus-4-5"]
    assert profile["has_secret"] is True
    assert_bound_inactive(harness, "claude-code", profile["id"])
    assert SECRET not in harness.client.get("/api/audit").text


def test_codex_local_endpoint_binds_codex_tool(tmp_path: Path, monkeypatch) -> None:
    config_dir = tmp_path / "codex"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(
        f'''model = "gpt-5"

[model_providers.custom]
name = "Codex 本机"
base_url = "https://api.example.com/v1"
wire_api = "responses"
experimental_bearer_token = "{SECRET}"
''',
        encoding="utf-8",
    )
    monkeypatch.setenv("CODEX_HOME", str(config_dir))
    harness = make_profile_harness(tmp_path / "app")

    preview_response = local_preview(harness, "codex-cli")
    assert preview_response.status_code == 200, preview_response.text
    assert preview_response.json()["source"] == "local_config"
    assert preview_response.json()["format"] == "toml"

    result = local_import(harness, "codex-cli")
    assert result.status_code == 201, result.text
    profile_id = result.json()["profile_ids"][0]
    assert_bound_inactive(harness, "codex-cli", profile_id)


def test_gemini_and_opencode_use_their_config_paths_without_secrets(
    tmp_path: Path, monkeypatch
) -> None:
    gemini_dir = tmp_path / "gemini"
    write_json(
        gemini_dir / "settings.json",
        {
            "baseUrl": "https://generativelanguage.googleapis.com/v1beta/openai/",
            "model": "gemini-2.5-pro",
        },
    )
    opencode_dir = tmp_path / "opencode"
    write_json(
        opencode_dir / "opencode.json",
        {
            "model": "gpt-5",
            "provider": {"openai": {"options": {"baseURL": "https://api.example.com/v1"}}},
        },
    )
    monkeypatch.setenv("GEMINI_CONFIG_DIR", str(gemini_dir))
    monkeypatch.setenv("OPENCODE_CONFIG_DIR", str(opencode_dir))
    harness = make_profile_harness(tmp_path / "app")

    gemini_preview = local_preview(harness, "gemini-cli")
    assert gemini_preview.status_code == 200, gemini_preview.text
    gemini_item = gemini_preview.json()["items"][0]
    assert gemini_item["has_secret"] is False
    assert any("API key" in note for note in gemini_item["notes"])

    gemini_result = local_import(harness, "gemini-cli")
    assert gemini_result.status_code == 201, gemini_result.text
    gemini_profile = harness.client.get(
        "/api/profiles/" + gemini_result.json()["profile_ids"][0]
    ).json()
    assert gemini_profile["name"] == "Gemini 本机配置"
    assert gemini_profile["base_url"].startswith("https://generativelanguage.googleapis.com")
    assert_bound_inactive(harness, "gemini-cli", gemini_profile["id"])

    opencode_preview = local_preview(harness, "opencode")
    assert opencode_preview.status_code == 200, opencode_preview.text
    assert opencode_preview.json()["items"][0]["has_secret"] is False
    opencode_result = local_import(harness, "opencode")
    assert opencode_result.status_code == 201, opencode_result.text
    opencode_profile = harness.client.get(
        "/api/profiles/" + opencode_result.json()["profile_ids"][0]
    ).json()
    assert opencode_profile["base_url"] == "https://api.example.com/v1"
    assert_bound_inactive(harness, "opencode", opencode_profile["id"])


def test_file_import_with_tool_id_binds_selected_tool(tmp_path: Path) -> None:
    harness = make_profile_harness(tmp_path / "app")
    payload = {
        "schema_version": 1,
        "profiles": [
            {
                "name": "文件导入",
                "protocol": "openai",
                "base_url": "https://api.example.com/v1",
                "models": [{"id": "gpt-5", "display_name": None}],
            }
        ],
    }
    response = harness.client.post(
        "/api/profiles/import",
        json={"content": json.dumps(payload), "tool_id": "codex-cli"},
    )
    assert response.status_code == 201, response.text
    assert_bound_inactive(harness, "codex-cli", response.json()["profile_ids"][0])


def test_local_import_missing_config_and_unknown_tool_are_readable(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "missing-claude"))
    harness = make_profile_harness(tmp_path / "app")

    missing = local_preview(harness, "claude-code")
    assert missing.status_code == 422
    assert missing.json()["code"] == "LOCAL_CONFIG_NOT_FOUND"

    unknown = local_preview(harness, "unknown-tool")
    assert unknown.status_code == 422
    assert unknown.json()["code"] == "LOCAL_IMPORT_UNSUPPORTED_TOOL"
