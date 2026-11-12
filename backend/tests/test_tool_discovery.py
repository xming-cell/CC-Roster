"""解析失败模型与服务隔离: T4 的行为测试。

适配器单测已经覆盖各文件格式的细节; 这里只断言服务层的可观察行为:
状态推导、warning 归并、单工具失败隔离, 以及错误消息不回显文件内容。
"""

import json
import os
from pathlib import Path
from typing import get_args

import pytest
from adapter_contract import deny_reads
from tool_fixtures import (
    StubAdapter,
    claude_adapter,
    codex_adapter,
    make_service,
    seed_claude,
    seed_codex,
    warning_codes,
    write_json,
)

from app.adapters.base import (
    ERROR_WARNING_CODES,
    ToolDetection,
    ToolWarning,
    WarningCode,
)
from app.core.errors import AppError

REQUIRED_WARNING_CODES = {
    "PARSE_ERROR",
    "PERMISSION_DENIED",
    "UNKNOWN_FORMAT",
    "UNSUPPORTED_VERSION",
    "CONFIG_EMPTY",
    "NO_MANAGED_FIELDS",
    "SECRET_IN_ENV",
    "ADAPTER_ERROR",
}


def test_list_tools_excludes_uninstalled_tools(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    codex_dir.mkdir()
    missing = StubAdapter(
        "missing-tool",
        detection=ToolDetection(installed=False, configured=False),
    )

    response = make_service(
        claude_adapter(claude_dir), codex_adapter(codex_dir), missing
    ).list_tools()

    assert [tool.id for tool in response.tools] == ["claude-code", "codex-cli"]
    assert [tool.status for tool in response.tools] == ["ok", "unconfigured"]
    assert response.warnings == []


def test_configured_tool_view_exposes_managed_fields(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    path = seed_claude(claude_dir)
    timestamp = 1_700_000_000
    os.utime(path, (timestamp, timestamp))

    response = make_service(claude_adapter(claude_dir)).list_tools()

    view = response.tools[0]
    assert view.id == "claude-code"
    assert view.display_name == "Claude Code"
    assert view.installed is True
    assert view.configured is True
    assert view.version is None
    assert view.provider == "Anthropic"
    assert view.base_url == "https://api.anthropic.com"
    assert view.model == "claude-sonnet-4"
    assert view.is_third_party is False
    assert view.config_path == str(path)
    assert view.last_modified is not None
    assert view.last_modified.tzinfo is not None
    assert int(view.last_modified.timestamp()) == timestamp
    assert view.has_secret is True
    assert view.secret_preview == "sk-a****cdef"
    assert view.warnings == []
    assert view.capabilities.read is True
    assert view.capabilities.write is True
    assert view.capabilities.sessions is False
    assert view.capabilities.launch is False
    assert view.capabilities.write_mode == "managed_fields"


def test_broken_config_marks_only_that_tool_as_error(tmp_path: Path) -> None:
    secret = "sk-broken-1234567890abcdef"
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text(
        '{"env": {"ANTHROPIC_AUTH_TOKEN": "' + secret + '"}',
        encoding="utf-8",
    )
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)

    response = make_service(claude_adapter(claude_dir), codex_adapter(codex_dir)).list_tools()

    claude, codex = response.tools
    assert claude.status == "error"
    assert codex.status == "ok"
    assert warning_codes(claude.warnings) == ["PARSE_ERROR"]
    assert "第 1 行第" in claude.warnings[0].message
    assert "列" in claude.warnings[0].message
    assert secret not in claude.model_dump_json()
    assert secret not in response.model_dump_json()
    assert codex.model == "gpt-5-codex"
    assert codex.provider == "OpenAI"
    assert response.warnings == []


def test_empty_and_unknown_configs_are_unconfigured_not_error(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("", encoding="utf-8")
    codex_dir = tmp_path / "codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text("[future]\nnested = true\n", encoding="utf-8")

    response = make_service(claude_adapter(claude_dir), codex_adapter(codex_dir)).list_tools()

    claude, codex = response.tools
    assert claude.status == "unconfigured"
    assert codex.status == "unconfigured"
    assert warning_codes(claude.warnings) == ["CONFIG_EMPTY"]
    assert warning_codes(codex.warnings) == ["NO_MANAGED_FIELDS"]


def test_detect_and_read_warnings_are_deduplicated(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    claude_dir.mkdir()
    (claude_dir / "settings.json").write_text("", encoding="utf-8")

    response = make_service(claude_adapter(claude_dir)).list_tools()

    assert warning_codes(response.tools[0].warnings) == ["CONFIG_EMPTY"]


def test_unsupported_schema_version_is_error_without_guessing_fields(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    write_json(claude_dir / "settings.json", {"schema_version": 2, "model": "claude-sonnet-4"})

    response = make_service(claude_adapter(claude_dir)).list_tools()

    view = response.tools[0]
    assert view.status == "error"
    assert view.model is None
    assert warning_codes(view.warnings) == ["UNSUPPORTED_VERSION"]


def test_unknown_wire_api_is_error_but_keeps_parsed_fields(tmp_path: Path) -> None:
    codex_dir = tmp_path / "codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        'model = "gpt-5-codex"\n'
        'model_provider = "openai"\n'
        "\n"
        "[model_providers.openai]\n"
        'base_url = "https://api.openai.com/v1"\n'
        'wire_api = "grpc"\n',
        encoding="utf-8",
    )

    response = make_service(codex_adapter(codex_dir)).list_tools()

    view = response.tools[0]
    assert view.status == "error"
    assert view.model == "gpt-5-codex"
    assert view.base_url == "https://api.openai.com/v1"
    assert warning_codes(view.warnings) == ["UNSUPPORTED_VERSION"]
    assert "wire_api" in view.warnings[0].message


def test_secret_in_env_warning_keeps_status_ok(tmp_path: Path) -> None:
    codex_dir = tmp_path / "codex"
    codex_dir.mkdir()
    (codex_dir / "config.toml").write_text(
        'model = "gpt-5-codex"\n'
        'model_provider = "openai"\n'
        "\n"
        "[model_providers.openai]\n"
        'base_url = "https://api.openai.com/v1"\n'
        'env_key = "MY_TEST_KEY"\n',
        encoding="utf-8",
    )

    response = make_service(codex_adapter(codex_dir)).list_tools()

    view = response.tools[0]
    assert view.status == "ok"
    assert view.has_secret is False
    assert warning_codes(view.warnings) == ["SECRET_IN_ENV"]


def test_permission_denied_marks_error_without_breaking_other_tools(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)
    claude = claude_adapter(claude_dir)

    with deny_reads(claude.managed_paths):
        response = make_service(claude, codex_adapter(codex_dir)).list_tools()

    denied, healthy = response.tools
    assert denied.status == "error"
    assert warning_codes(denied.warnings) == ["PERMISSION_DENIED"]
    assert healthy.status == "ok"


@pytest.mark.parametrize("stage", ["detect", "read"])
def test_adapter_exception_is_isolated_into_top_level_warning(tmp_path: Path, stage: str) -> None:
    secret = "sk-exploding-1234567890abcdef"
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)
    exploding = StubAdapter(
        "exploding-tool",
        detection=ToolDetection(installed=True, configured=True),
        error=RuntimeError(f"boom {secret}"),
        error_stage=stage,
    )

    response = make_service(exploding, codex_adapter(codex_dir)).list_tools()

    assert [tool.id for tool in response.tools] == ["codex-cli"]
    assert len(response.warnings) == 1
    assert response.warnings[0].code == "ADAPTER_ERROR"
    assert "exploding-tool" in response.warnings[0].message
    assert secret not in response.model_dump_json()
    assert "Traceback" not in response.model_dump_json()


def test_get_tool_returns_single_view(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)

    view = make_service(claude_adapter(claude_dir)).get_tool("claude-code")

    assert view.id == "claude-code"
    assert view.status == "ok"
    assert view.model == "claude-sonnet-4"


def test_get_tool_unknown_id_raises_tool_not_found(tmp_path: Path) -> None:
    service = make_service(claude_adapter(tmp_path / "missing"))

    with pytest.raises(AppError) as excinfo:
        service.get_tool("not-a-tool")

    assert excinfo.value.code == "TOOL_NOT_FOUND"
    assert excinfo.value.status_code == 404


def test_get_tool_uninstalled_tool_raises_tool_not_found(tmp_path: Path) -> None:
    service = make_service(claude_adapter(tmp_path / "missing"))

    with pytest.raises(AppError) as excinfo:
        service.get_tool("claude-code")

    assert excinfo.value.code == "TOOL_NOT_FOUND"
    assert excinfo.value.status_code == 404


def test_get_tool_adapter_exception_raises_adapter_error_without_echo(tmp_path: Path) -> None:
    secret = "sk-exploding-1234567890abcdef"
    service = make_service(
        StubAdapter("exploding-tool", error=RuntimeError(f"boom {secret}")),
    )

    with pytest.raises(AppError) as excinfo:
        service.get_tool("exploding-tool")

    assert excinfo.value.code == "ADAPTER_ERROR"
    assert excinfo.value.status_code == 500
    assert secret not in excinfo.value.message
    assert "Traceback" not in excinfo.value.message


def test_list_reflects_config_changes_between_calls(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    path = seed_claude(claude_dir, model="first-model")
    service = make_service(claude_adapter(claude_dir))
    assert service.list_tools().tools[0].model == "first-model"

    path.write_text(json.dumps({"model": "second-model"}), encoding="utf-8")

    assert service.list_tools().tools[0].model == "second-model"


def test_list_tools_filters_by_name_provider_model_and_status(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)

    response = make_service(claude_adapter(claude_dir), codex_adapter(codex_dir)).list_tools(
        name="  claude  ",
        provider="anthropic",
        model="sonnet",
        status="ok",
    )

    assert [tool.id for tool in response.tools] == ["claude-code"]


def test_list_tools_ignores_blank_filters_and_keeps_original_order(tmp_path: Path) -> None:
    claude_dir = tmp_path / "claude"
    seed_claude(claude_dir)
    codex_dir = tmp_path / "codex"
    seed_codex(codex_dir)

    response = make_service(claude_adapter(claude_dir), codex_adapter(codex_dir)).list_tools(
        name=" ",
        provider="",
        model="\t",
        status=None,
    )

    assert [tool.id for tool in response.tools] == ["claude-code", "codex-cli"]


def test_warning_code_contract_covers_required_failures() -> None:
    codes = set(get_args(WarningCode))

    assert codes >= REQUIRED_WARNING_CODES
    assert codes >= ERROR_WARNING_CODES


def test_unknown_warning_code_is_rejected() -> None:
    with pytest.raises(ValueError):
        ToolWarning.model_validate({"code": "SOMETHING_ELSE", "message": "x"})
