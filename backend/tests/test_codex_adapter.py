import json
import os
from pathlib import Path

import pytest
from adapter_contract import AdapterContract

from app.adapters.base import ToolAdapter
from app.adapters.codex_cli import CodexCliAdapter, resolve_codex_config_dir

CONFIG_FILE = "config.toml"
AUTH_FILE = "auth.json"
AUTH_KEY = "sk-openai-1234567890abcdef"


def make_adapter(config_dir: Path) -> CodexCliAdapter:
    return CodexCliAdapter(config_dir, which=lambda _name: None)


def write_config(config_dir: Path, text: str) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / CONFIG_FILE
    path.write_text(text, encoding="utf-8")
    return path


def write_auth(config_dir: Path, data: object) -> Path:
    config_dir.mkdir(parents=True, exist_ok=True)
    path = config_dir / AUTH_FILE
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


CONFIGURED_TOML = """\
model = "gpt-5-codex"
model_provider = "openai"

[model_providers.openai]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
wire_api = "responses"
"""


class TestCodexAdapterContract(AdapterContract):
    def make_adapter(self, config_dir: Path) -> ToolAdapter:
        return CodexCliAdapter(config_dir, which=lambda _name: None)

    def seed_configured(self, config_dir: Path) -> None:
        write_config(config_dir, CONFIGURED_TOML)
        write_auth(config_dir, {"OPENAI_API_KEY": AUTH_KEY})

    def seed_unknown_structure(self, config_dir: Path) -> None:
        write_config(config_dir, "[future]\nnested = true\n")


def test_resolve_config_dir_prefers_env_override(tmp_path: Path) -> None:
    custom = tmp_path / "custom-codex"

    resolved = resolve_codex_config_dir(environ={"CODEX_HOME": str(custom)}, home=tmp_path / "home")

    assert resolved == custom


def test_resolve_config_dir_falls_back_to_home_for_empty_env(tmp_path: Path) -> None:
    home = tmp_path / "home"

    resolved = resolve_codex_config_dir(environ={"CODEX_HOME": ""}, home=home)

    assert resolved == home / ".codex"


def test_resolve_config_dir_treats_relative_path_as_home_relative(tmp_path: Path) -> None:
    home = tmp_path / "home"

    resolved = resolve_codex_config_dir(environ={"CODEX_HOME": "profiles/codex"}, home=home)

    assert resolved == home / "profiles" / "codex"


def test_configured_config_is_detected_and_read(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    path = write_config(config_dir, CONFIGURED_TOML)
    write_auth(config_dir, {"OPENAI_API_KEY": AUTH_KEY})
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

    assert result.provider == "OpenAI"
    assert result.base_url == "https://api.openai.com/v1"
    assert result.model == "gpt-5-codex"
    assert result.is_third_party is False
    assert result.has_secret is True
    assert result.secret_preview == "sk-o****cdef"
    assert result.warnings == []


def test_custom_provider_is_third_party(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(
        config_dir,
        """\
model = "gpt-5-codex"
model_provider = "relay"

[model_providers.relay]
name = "My Relay"
base_url = "https://relay.example.com/v1"
wire_api = "chat"
""",
    )

    result = make_adapter(config_dir).read()

    assert result.provider == "My Relay"
    assert result.base_url == "https://relay.example.com/v1"
    assert result.is_third_party is True
    assert result.warnings == []


def test_openai_provider_with_custom_base_url_is_third_party(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(
        config_dir,
        """\
model_provider = "openai"

[model_providers.openai]
base_url = "https://relay.example.com/v1"
""",
    )

    result = make_adapter(config_dir).read()

    assert result.provider == "OpenAI"
    assert result.is_third_party is True


def test_openai_provider_without_base_url_is_official(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(
        config_dir,
        """\
model_provider = "openai"

[model_providers.openai]
name = "OpenAI"
""",
    )

    result = make_adapter(config_dir).read()

    assert result.is_third_party is False
    assert result.warnings == []


def test_builtin_openai_provider_does_not_need_a_table(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, 'model = "gpt-5-codex"\nmodel_provider = "openai"\n')

    result = make_adapter(config_dir).read()

    assert result.provider == "OpenAI"
    assert result.is_third_party is False
    assert result.warnings == []


def test_missing_provider_is_reported(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, 'model = "gpt-5-codex"\nmodel_provider = "relay"\n')

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNKNOWN_FORMAT"]
    assert "model_provider" in result.warnings[0].message
    assert result.provider == "relay"
    assert result.base_url is None
    assert result.is_third_party is True


def test_unknown_wire_api_is_unsupported_version(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(
        config_dir,
        """\
model = "gpt-5-codex"
model_provider = "openai"

[model_providers.openai]
base_url = "https://api.openai.com/v1"
wire_api = "grpc"
""",
    )

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNSUPPORTED_VERSION"]
    assert "wire_api" in result.warnings[0].message
    assert result.model == "gpt-5-codex"
    assert result.base_url == "https://api.openai.com/v1"


@pytest.mark.parametrize("wire_api", ["chat", "responses"])
def test_known_wire_api_values_are_accepted(tmp_path: Path, wire_api: str) -> None:
    config_dir = tmp_path / "codex"
    write_config(
        config_dir,
        f"""\
model_provider = "openai"

[model_providers.openai]
base_url = "https://api.openai.com/v1"
wire_api = "{wire_api}"
""",
    )

    result = make_adapter(config_dir).read()

    assert result.warnings == []


def test_broken_toml_reports_position_without_echoing_secret(tmp_path: Path) -> None:
    secret = "sk-broken-1234567890abcdef"
    config_dir = tmp_path / "codex"
    write_config(config_dir, f'model = "{secret}"\nmodel_provider = "openai\n')

    adapter = make_adapter(config_dir)
    detection = adapter.detect()
    result = adapter.read()

    assert detection.configured is False
    assert [warning.code for warning in detection.warnings] == ["PARSE_ERROR"]
    assert "第 2 行第" in detection.warnings[0].message
    assert "列" in detection.warnings[0].message
    assert secret not in detection.warnings[0].message
    assert secret not in result.model_dump_json()


def test_empty_config_file_is_unconfigured(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, "")

    adapter = make_adapter(config_dir)
    detection = adapter.detect()

    assert detection.installed is True
    assert detection.configured is False
    assert [warning.code for warning in detection.warnings] == ["CONFIG_EMPTY"]


def test_empty_config_dir_is_unconfigured_without_warning(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    config_dir.mkdir()

    detection = make_adapter(config_dir).detect()

    assert detection.installed is True
    assert detection.configured is False
    assert detection.warnings == []


def test_auth_file_is_optional(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, CONFIGURED_TOML)

    result = make_adapter(config_dir).read()

    assert result.has_secret is False
    assert result.secret_preview is None
    assert result.warnings == []


def test_broken_auth_json_keeps_config_fields(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, CONFIGURED_TOML)
    (config_dir / AUTH_FILE).write_text("{not json", encoding="utf-8")

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["PARSE_ERROR"]
    assert result.model == "gpt-5-codex"
    assert result.provider == "OpenAI"
    assert result.has_secret is False


def test_oauth_tokens_in_auth_json_are_not_read(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, CONFIGURED_TOML)
    oauth_secret = "sk-oauth-1234567890abcdef"
    write_auth(
        config_dir,
        {"tokens": {"access_token": oauth_secret}, "last_refresh": "2026-01-01"},
    )

    result = make_adapter(config_dir).read()

    assert result.has_secret is False
    assert result.secret_preview is None
    assert result.warnings == []
    assert oauth_secret not in result.model_dump_json()


def test_env_key_is_hint_only_and_not_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "codex"
    write_config(
        config_dir,
        """\
model_provider = "openai"

[model_providers.openai]
base_url = "https://api.openai.com/v1"
env_key = "MY_TEST_KEY"
""",
    )
    env_secret = "sk-from-env-1234567890abcdef"
    monkeypatch.setenv("MY_TEST_KEY", env_secret)

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["SECRET_IN_ENV"]
    assert "MY_TEST_KEY" in result.warnings[0].message
    assert result.has_secret is False
    assert env_secret not in result.model_dump_json()


def test_missing_model_provider_has_no_third_party_conclusion(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, 'model = "gpt-5-codex"\n')

    result = make_adapter(config_dir).read()

    assert result.model == "gpt-5-codex"
    assert result.provider is None
    assert result.is_third_party is None
    assert result.warnings == []


def test_model_not_string_is_unknown_format(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, "model = 42\n")

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNKNOWN_FORMAT"]
    assert result.model is None


def test_model_providers_not_table_is_unknown_format(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, 'model = "gpt-5-codex"\nmodel_providers = "oops"\n')

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNKNOWN_FORMAT"]
    assert result.model == "gpt-5-codex"


def test_provider_entry_not_table_is_unknown_format(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(
        config_dir,
        'model = "gpt-5-codex"\nmodel_provider = "relay"\nmodel_providers = { relay = "oops" }\n',
    )

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNKNOWN_FORMAT"]
    assert result.provider == "relay"
    assert result.base_url is None
    assert result.is_third_party is True


def test_unsupported_schema_version_does_not_guess_fields(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    write_config(config_dir, 'schema_version = 2\nmodel = "gpt-5-codex"\n')

    result = make_adapter(config_dir).read()

    assert [warning.code for warning in result.warnings] == ["UNSUPPORTED_VERSION"]
    assert result.model is None


def test_installed_via_executable_when_config_dir_missing(tmp_path: Path) -> None:
    adapter = CodexCliAdapter(
        tmp_path / "missing",
        which=lambda name: "/usr/local/bin/codex" if name == "codex" else None,
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
    file_instead_of_dir = tmp_path / "codex"
    file_instead_of_dir.write_text("not a directory", encoding="utf-8")

    detection = make_adapter(file_instead_of_dir).detect()

    assert detection.installed is False
    assert detection.configured is False
    assert detection.warnings == []


def test_reads_reflect_file_changes_without_cache(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    path = write_config(config_dir, 'model = "first-model"\n')
    adapter = make_adapter(config_dir)
    assert adapter.read().model == "first-model"

    path.write_text('model = "second-model"\n', encoding="utf-8")
    os.utime(path, (1_700_000_100, 1_700_000_100))

    detection = adapter.detect()
    assert adapter.read().model == "second-model"
    assert detection.last_modified is not None
    assert int(detection.last_modified.timestamp()) == 1_700_000_100


def test_last_modified_falls_back_to_auth_file(tmp_path: Path) -> None:
    config_dir = tmp_path / "codex"
    config_dir.mkdir()
    auth_path = write_auth(config_dir, {"OPENAI_API_KEY": AUTH_KEY})
    os.utime(auth_path, (1_700_000_200, 1_700_000_200))

    detection = make_adapter(config_dir).detect()

    assert detection.configured is True
    assert detection.last_modified is not None
    assert int(detection.last_modified.timestamp()) == 1_700_000_200
