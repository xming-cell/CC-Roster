import json
import os
from pathlib import Path

import pytest
from adapter_contract import AdapterContract

from app.adapters.base import ToolAdapter
from app.adapters.claude_code import ClaudeCodeAdapter, resolve_claude_config_dir

SETTINGS_FILE = "settings.json"
AUTH_TOKEN = "sk-ant-1234567890abcdef"


def make_adapter(config_dir: Path) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(config_dir, which=lambda _name: None)


def write_settings(config_dir: Path, data: object) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / SETTINGS_FILE
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class TestClaudeAdapterContract(AdapterContract):
    def make_adapter(self, config_dir: Path) -> ToolAdapter:
        return ClaudeCodeAdapter(config_dir, which=lambda _name: None)

    def seed_configured(self, config_dir: Path) -> None:
        write_settings(
            config_dir,
            {
                "model": "claude-sonnet-4",
                "env": {
                    "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
                    "ANTHROPIC_AUTH_TOKEN": AUTH_TOKEN,
                },
            },
        )

    def seed_unknown_structure(self, config_dir: Path) -> None:
        write_settings(config_dir, {"future": {"nested": True}})


def test_resolve_config_dir_prefers_env_override(tmp_path: Path) -> None:
    custom = tmp_path / "custom-claude"

    resolved = resolve_claude_config_dir(
        environ={"CLAUDE_CONFIG_DIR": str(custom)}, home=tmp_path / "home"
    )

    assert resolved == custom


def test_resolve_config_dir_falls_back_to_home_for_empty_env(tmp_path: Path) -> None:
    home = tmp_path / "home"

    resolved = resolve_claude_config_dir(environ={"CLAUDE_CONFIG_DIR": ""}, home=home)

    assert resolved == home / ".claude"


def test_resolve_config_dir_treats_relative_path_as_home_relative(tmp_path: Path) -> None:
    home = tmp_path / "home"

    resolved = resolve_claude_config_dir(
        environ={"CLAUDE_CONFIG_DIR": "profiles/claude"}, home=home
    )

    assert resolved == home / "profiles" / "claude"


def test_configured_settings_are_detected_and_read(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    path = write_settings(
        config_dir,
        {
            "model": "claude-sonnet-4",
            "env": {
                "ANTHROPIC_BASE_URL": "https://relay.example.com",
                "ANTHROPIC_AUTH_TOKEN": AUTH_TOKEN,
                "ANTHROPIC_API_KEY": "api-key-should-not-win-0000",
            },
        },
    )
    timestamp = 1_700_000_000
    os.utime(path, (timestamp, timestamp))
    adapter = make_adapter(config_dir)

    detection = adapter.detect()

    assert detection.installed is True
    assert detection.configured is True
    assert detection.warnings == []
    assert detection.config_path == str(path)
    assert detection.last_modified is not None
    assert detection.last_modified.tzinfo is not None
    assert int(detection.last_modified.timestamp()) == timestamp

    result = adapter.read()

    assert result.provider == "Anthropic"
    assert result.base_url == "https://relay.example.com"
    assert result.model == "claude-sonnet-4"
    assert result.is_third_party is True
    assert result.has_secret is True
    assert result.secret_preview == "sk-a****cdef"
    assert result.warnings == []


def test_env_model_overrides_top_level_model(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    write_settings(
        config_dir,
        {"model": "top-level-model", "env": {"ANTHROPIC_MODEL": "env-model"}},
    )

    result = make_adapter(config_dir).read()

    assert result.model == "env-model"


@pytest.mark.parametrize(
    "base_url",
    [None, "https://api.anthropic.com", "https://API.ANTHROPIC.COM/v1"],
)
def test_official_or_missing_base_url_is_not_third_party(
    tmp_path: Path, base_url: str | None
) -> None:
    env: dict[str, str] = {"ANTHROPIC_MODEL": "claude-sonnet-4"}
    if base_url is not None:
        env["ANTHROPIC_BASE_URL"] = base_url
    config_dir = tmp_path / "claude"
    write_settings(config_dir, {"env": env})

    result = make_adapter(config_dir).read()

    assert result.is_third_party is False
    assert result.warnings == []


def test_unknown_fields_only_are_unconfigured_with_warning(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    write_settings(config_dir, {"theme": "dark", "env": {"SOMETHING_ELSE": "x"}})
    adapter = make_adapter(config_dir)

    detection = adapter.detect()
    result = adapter.read()

    assert detection.configured is False
    assert [warning.code for warning in detection.warnings] == ["NO_MANAGED_FIELDS"]
    assert result.provider is None
    assert result.model is None
    assert result.is_third_party is None
    assert result.has_secret is False
    assert result.secret_preview is None


def test_empty_settings_file_is_unconfigured(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    config_dir.mkdir()
    (config_dir / SETTINGS_FILE).write_text("", encoding="utf-8")
    adapter = make_adapter(config_dir)

    detection = adapter.detect()
    result = adapter.read()

    assert detection.installed is True
    assert detection.configured is False
    assert [warning.code for warning in detection.warnings] == ["CONFIG_EMPTY"]
    assert [warning.code for warning in result.warnings] == ["CONFIG_EMPTY"]


def test_broken_json_reports_position_without_echoing_secret(tmp_path: Path) -> None:
    secret = "sk-broken-1234567890abcdef"
    config_dir = tmp_path / "claude"
    config_dir.mkdir()
    (config_dir / SETTINGS_FILE).write_text(
        '{"env": {"ANTHROPIC_AUTH_TOKEN": "' + secret + '"}',
        encoding="utf-8",
    )
    adapter = make_adapter(config_dir)

    detection = adapter.detect()
    result = adapter.read()

    assert detection.configured is False
    assert [warning.code for warning in detection.warnings] == ["PARSE_ERROR"]
    assert "第 1 行第" in detection.warnings[0].message
    assert "列" in detection.warnings[0].message
    assert secret not in detection.warnings[0].message
    assert secret not in result.model_dump_json()


def test_top_level_not_object_is_unknown_format(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    write_settings(config_dir, ["not", "an", "object"])

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNKNOWN_FORMAT"]
    assert result.model is None


def test_env_not_object_is_unknown_format(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    write_settings(config_dir, {"model": "claude-sonnet-4", "env": "oops"})

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNKNOWN_FORMAT"]
    assert result.model == "claude-sonnet-4"


def test_model_not_string_is_unknown_format(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    write_settings(config_dir, {"model": 42})

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNKNOWN_FORMAT"]
    assert result.model is None
    assert result.provider is None


def test_unsupported_schema_version_does_not_guess_fields(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    write_settings(config_dir, {"schema_version": 2, "model": "claude-sonnet-4"})

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNSUPPORTED_VERSION"]
    assert result.model is None


def test_installed_via_executable_when_config_dir_missing(tmp_path: Path) -> None:
    adapter = ClaudeCodeAdapter(
        tmp_path / "missing",
        which=lambda name: "/usr/local/bin/claude" if name == "claude" else None,
    )

    detection = adapter.detect()

    assert detection.installed is True
    assert detection.configured is False
    assert detection.warnings == []
    assert detection.last_modified is None


def test_not_installed_when_no_config_dir_and_no_executable(tmp_path: Path) -> None:
    detection = make_adapter(tmp_path / "missing").detect()

    assert detection.installed is False


def test_config_path_pointing_to_a_file_does_not_crash(tmp_path: Path) -> None:
    file_instead_of_dir = tmp_path / "claude"
    file_instead_of_dir.write_text("not a directory", encoding="utf-8")

    detection = make_adapter(file_instead_of_dir).detect()

    assert detection.installed is False
    assert detection.configured is False
    assert detection.warnings == []


def test_reads_reflect_file_changes_without_cache(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    path = write_settings(config_dir, {"model": "first-model"})
    adapter = make_adapter(config_dir)
    assert adapter.read().model == "first-model"

    path.write_text(json.dumps({"model": "second-model"}), encoding="utf-8")
    os.utime(path, (1_700_000_100, 1_700_000_100))

    detection = adapter.detect()
    assert adapter.read().model == "second-model"
    assert detection.last_modified is not None
    assert int(detection.last_modified.timestamp()) == 1_700_000_100


def test_short_secret_is_fully_masked(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    write_settings(config_dir, {"env": {"ANTHROPIC_AUTH_TOKEN": "short"}})

    result = make_adapter(config_dir).read()

    assert result.has_secret is True
    assert result.secret_preview == "****"


def test_oauth_credentials_file_is_not_read(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    write_settings(
        config_dir,
        {"model": "claude-sonnet-4", "env": {"ANTHROPIC_BASE_URL": "https://api.anthropic.com"}},
    )
    oauth_secret = "sk-oauth-1234567890abcdef"
    (config_dir / ".credentials.json").write_text(
        json.dumps({"claudeAiOauth": {"accessToken": oauth_secret}}),
        encoding="utf-8",
    )
    adapter = make_adapter(config_dir)

    result = adapter.read()

    assert result.has_secret is False
    assert result.secret_preview is None
    assert oauth_secret not in result.model_dump_json()
    assert config_dir / ".credentials.json" not in adapter.managed_paths


def test_read_after_file_deleted_returns_empty_without_raising(tmp_path: Path) -> None:
    config_dir = tmp_path / "claude"
    path = write_settings(config_dir, {"model": "claude-sonnet-4"})
    adapter = make_adapter(config_dir)
    assert adapter.detect().configured is True

    path.unlink()

    result = adapter.read()

    assert result.model is None
    assert result.warnings == []
