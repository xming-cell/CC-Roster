"""008 T1: 适配器写契约、共享渲染与两个工具的字段映射。

这些测试只读 `ToolCurrentFile` 内存字节, 不落盘; 保真性由「渲染后未托管内容不变」
断言, 真正的原子写与快照由 007 的写引擎测试覆盖。
"""

import json
from collections.abc import Mapping
from pathlib import Path

import pytest
from profile_fixtures import make_profile

from app.adapters.base import (
    ToolCurrentFile,
    ToolPlan,
    ToolPlanFile,
)
from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.core.errors import AppError

CLAUDE_SECRET = "sk-ant-contract-1234567890abcdef"
CODEX_SECRET = "sk-openai-contract-1234567890"
NEW_MODEL = "contract-new-model"

CLAUDE_BYTES = (
    "﻿{\r\n"
    '  "env": {\r\n'
    '    "ANTHROPIC_BASE_URL": "https://old.example.com",\r\n'
    '    "KEEP_ME": "原样保留",\r\n'
    '    "ANTHROPIC_AUTH_TOKEN": "old-token-1234567890"\r\n'
    "  },\r\n"
    '  "model": "old-model",\r\n'
    '  "hooks": {"Stop": [{"command": "echo hi"}]},\r\n'
    '  "unknown": [1, 2, 3]\r\n'
    "}\r\n"
).encode()

CODEX_CONFIG = (
    "# 顶部注释, 不得丢失\r\n"
    'model = "gpt-old"\r\n'
    'approval_policy = "never"\r\n'
    "\r\n"
    "[model_providers.openai]\r\n"
    'name = "旧名字"\r\n'
    'base_url = "https://old.example.com/v1"\r\n'
    'wire_api = "chat"\r\n'
    "requires_openai_auth = true\r\n"
    "\r\n"
    "[mcp_servers.demo]\r\n"
    'command = "demo"\r\n'
).encode()

CODEX_AUTH = {
    "tokens": {"id_token": "oauth-id-token"},
    "last_refresh": "2026-01-01T00:00:00Z",
    "OPENAI_API_KEY": "sk-old-openai-key",
}


def claude_adapter(tmp_path: Path) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(tmp_path / "claude", which=lambda _name: None)


def codex_adapter(tmp_path: Path) -> CodexCliAdapter:
    return CodexCliAdapter(tmp_path / "codex", which=lambda _name: None)


def claude_current(
    adapter: ClaudeCodeAdapter,
    content: bytes | str | None,
) -> dict[str, ToolCurrentFile]:
    path = adapter.managed_paths[0]
    if content is None:
        return {str(path): ToolCurrentFile(path=str(path), exists=False)}
    data = content.encode() if isinstance(content, str) else content
    return {str(path): ToolCurrentFile(path=str(path), exists=True, data=data)}


def codex_current(
    adapter: CodexCliAdapter,
    config: bytes | str | None,
    auth: Mapping[str, object] | None,
) -> dict[str, ToolCurrentFile]:
    config_path, auth_path = adapter.managed_paths
    result: dict[str, ToolCurrentFile] = {}
    if config is None:
        result[str(config_path)] = ToolCurrentFile(path=str(config_path), exists=False)
    else:
        data = config.encode() if isinstance(config, str) else config
        result[str(config_path)] = ToolCurrentFile(path=str(config_path), exists=True, data=data)
    if auth is None:
        result[str(auth_path)] = ToolCurrentFile(path=str(auth_path), exists=False)
    else:
        data = json.dumps(auth, ensure_ascii=False).encode()
        result[str(auth_path)] = ToolCurrentFile(path=str(auth_path), exists=True, data=data)
    return result


def plan_file(plan: ToolPlan, path: Path) -> ToolPlanFile:
    return next(item for item in plan.files if item.path == str(path))


def claude_plan(
    adapter: ClaudeCodeAdapter,
    content: bytes | str | None,
    *,
    secret: str | None = CLAUDE_SECRET,
    model: str | None = NEW_MODEL,
    profile_name: str = "Claude 档案",
    base_url: str = "https://relay.example.com",
) -> ToolPlan:
    profile = make_profile(profile_name, base_url=base_url)
    return adapter.plan(
        profile,
        secret=secret,
        model=model,
        current=claude_current(adapter, content),
    )


def codex_plan(
    adapter: CodexCliAdapter,
    config: bytes | str | None,
    auth: Mapping[str, object] | None,
    *,
    secret: str | None = CODEX_SECRET,
    model: str | None = NEW_MODEL,
    profile_name: str = "Codex 档案",
    base_url: str = "https://relay.example.com/v1",
) -> ToolPlan:
    profile = make_profile(
        profile_name,
        protocol="openai",
        base_url=base_url,
    )
    return adapter.plan(
        profile,
        secret=secret,
        model=model,
        current=codex_current(adapter, config, auth),
    )


# ---------------------------------------------------------------------------
# 契约基线
# ---------------------------------------------------------------------------


def test_both_adapters_declare_write_capability_and_protocols(
    tmp_path: Path,
) -> None:
    claude = claude_adapter(tmp_path)
    codex = codex_adapter(tmp_path)

    assert claude.capabilities.write is True
    assert claude.capabilities.write_mode == "managed_fields"
    assert claude.supported_protocols == ("anthropic",)
    assert codex.capabilities.write is True
    assert codex.capabilities.write_mode == "managed_fields"
    assert codex.supported_protocols == ("openai",)


def test_plan_does_not_touch_disk_and_is_deterministic(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)
    config_dir = tmp_path / "codex"
    config_dir.mkdir()
    config_path = config_dir / "config.toml"
    auth_path = config_dir / "auth.json"
    config_path.write_bytes(CODEX_CONFIG)
    auth_path.write_text(json.dumps(CODEX_AUTH), encoding="utf-8")

    first = codex_plan(adapter, config_path.read_bytes(), CODEX_AUTH)
    second = codex_plan(adapter, config_path.read_bytes(), CODEX_AUTH)

    assert config_path.read_bytes() == CODEX_CONFIG
    assert sorted(path.name for path in config_dir.iterdir()) == [
        "auth.json",
        "config.toml",
    ]
    assert first.model_dump() == second.model_dump()


def test_render_is_pure_and_repeatable(tmp_path: Path) -> None:
    adapter = claude_adapter(tmp_path)
    plan = claude_plan(adapter, CLAUDE_BYTES)
    target = plan_file(plan, adapter.managed_paths[0])

    first = adapter.render(target, CLAUDE_BYTES)
    second = adapter.render(target, CLAUDE_BYTES)

    assert first == second
    assert CLAUDE_BYTES.startswith(b"\xef\xbb\xbf")
    adapter.verify(target, CLAUDE_BYTES, first)


def test_claude_preserves_bom_crlf_order_and_unknown_fields(
    tmp_path: Path,
) -> None:
    adapter = claude_adapter(tmp_path)
    plan = claude_plan(adapter, CLAUDE_BYTES)
    target = plan_file(plan, adapter.managed_paths[0])

    rendered = adapter.render(target, CLAUDE_BYTES)
    text = rendered.decode("utf-8-sig")

    assert rendered.startswith(b"\xef\xbb\xbf")
    assert b"\r\n" in rendered
    assert '"KEEP_ME": "原样保留"' in text
    assert '"hooks"' in text
    assert '"unknown": [1, 2, 3]' in text
    assert '"command": "echo hi"' in text
    parsed = json.loads(text)
    assert parsed["env"]["ANTHROPIC_BASE_URL"] == "https://relay.example.com"
    assert parsed["model"] == NEW_MODEL
    assert parsed["env"]["ANTHROPIC_AUTH_TOKEN"] == CLAUDE_SECRET
    assert "ANTHROPIC_API_KEY" not in parsed["env"]
    assert parsed["hooks"] == {"Stop": [{"command": "echo hi"}]}
    assert list(parsed) == ["env", "model", "hooks", "unknown"]


def test_codex_preserves_comments_crlf_and_unmanaged_tables(
    tmp_path: Path,
) -> None:
    adapter = codex_adapter(tmp_path)
    plan = codex_plan(adapter, CODEX_CONFIG, CODEX_AUTH)
    target = plan_file(plan, adapter.managed_paths[0])

    rendered = adapter.render(target, CODEX_CONFIG)
    text = rendered.decode("utf-8")

    assert "# 顶部注释, 不得丢失" in text
    assert b"\r\n" in rendered
    assert 'approval_policy = "never"' in text
    assert "requires_openai_auth = true" in text
    assert "[mcp_servers.demo]" in text
    assert 'command = "demo"' in text
    assert text.index("model = ") < text.index("approval_policy")
    assert 'model = "contract-new-model"' in text
    assert 'model_provider = "openai"' in text
    assert "[model_providers.openai]" in text
    assert 'name = "Codex 档案"' in text
    assert 'base_url = "https://relay.example.com/v1"' in text
    assert 'wire_api = "chat"' in text
    adapter.verify(target, CODEX_CONFIG, rendered)


def test_verify_detects_target_and_unknown_tampering(tmp_path: Path) -> None:
    adapter = claude_adapter(tmp_path)
    plan = claude_plan(adapter, CLAUDE_BYTES)
    target = plan_file(plan, adapter.managed_paths[0])
    rendered = adapter.render(target, CLAUDE_BYTES)

    target_tampered = rendered.replace(NEW_MODEL.encode(), b"tampered-model")
    with pytest.raises(AppError) as target_error:
        adapter.verify(target, CLAUDE_BYTES, target_tampered)
    assert target_error.value.code == "WRITE_VERIFY_FAILED"

    unknown_tampered = rendered.replace(
        '"KEEP_ME": "原样保留"'.encode(),
        '"KEEP_ME": "被篡改"'.encode(),
    )
    with pytest.raises(AppError) as unknown_error:
        adapter.verify(target, CLAUDE_BYTES, unknown_tampered)
    assert unknown_error.value.code == "WRITE_VERIFY_FAILED"


def test_unsupported_structures_become_unsafe_write_blockers(
    tmp_path: Path,
) -> None:
    adapter = claude_adapter(tmp_path)

    array_plan = claude_plan(adapter, b"[]")
    assert [blocker.code for blocker in array_plan.blockers] == ["UNSAFE_WRITE"]
    assert array_plan.files == []

    env_plan = claude_plan(adapter, '{"env": []}')
    assert [blocker.code for blocker in env_plan.blockers] == ["UNSAFE_WRITE"]


def test_parse_errors_become_blockers_without_file_content(
    tmp_path: Path,
) -> None:
    adapter = claude_adapter(tmp_path)
    plan = claude_plan(adapter, '{"env": ')

    assert [blocker.code for blocker in plan.blockers] == ["PARSE_ERROR"]
    assert "第 1 行" in plan.blockers[0].message
    assert plan.files == []


def test_codex_non_table_provider_structure_is_unsafe(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)

    providers = codex_plan(adapter, 'model_providers = "x"\n', None)
    assert [blocker.code for blocker in providers.blockers] == ["UNSAFE_WRITE"]

    openai = codex_plan(adapter, '[model_providers]\nopenai = "x"\n', None)
    assert [blocker.code for blocker in openai.blockers] == ["UNSAFE_WRITE"]


def test_unsupported_schema_version_blocks_both_adapters(tmp_path: Path) -> None:
    claude = claude_adapter(tmp_path)
    claude_result = claude_plan(claude, '{"schema_version": 2}')
    assert [blocker.code for blocker in claude_result.blockers] == ["UNSUPPORTED_VERSION"]

    codex = codex_adapter(tmp_path)
    codex_result = codex_plan(codex, "schema_version = 2\n", None)
    assert [blocker.code for blocker in codex_result.blockers] == ["UNSUPPORTED_VERSION"]


# ---------------------------------------------------------------------------
# Claude Code 映射
# ---------------------------------------------------------------------------


def test_claude_missing_file_creates_minimal_settings(tmp_path: Path) -> None:
    adapter = claude_adapter(tmp_path)
    plan = claude_plan(adapter, None)
    target = plan_file(plan, adapter.managed_paths[0])

    assert plan.blockers == []
    assert target.create is True
    rendered = adapter.render(target, b"")
    adapter.verify(target, b"", rendered)

    parsed = json.loads(rendered)
    assert parsed["env"]["ANTHROPIC_BASE_URL"] == "https://relay.example.com"
    assert parsed["env"]["ANTHROPIC_MODEL"] == NEW_MODEL
    assert parsed["env"]["ANTHROPIC_AUTH_TOKEN"] == CLAUDE_SECRET
    assert plan.restart_required is True
    assert "重启" in plan.restart_message


def test_claude_official_host_uses_api_key(tmp_path: Path) -> None:
    adapter = claude_adapter(tmp_path)
    content = b'{"env": {"ANTHROPIC_BASE_URL": "https://api.anthropic.com"}}'
    plan = claude_plan(
        adapter,
        content,
        base_url="https://api.anthropic.com",
    )
    target = plan_file(plan, adapter.managed_paths[0])

    rendered = adapter.render(target, content)
    parsed = json.loads(rendered)
    assert parsed["env"]["ANTHROPIC_API_KEY"] == CLAUDE_SECRET
    assert "ANTHROPIC_AUTH_TOKEN" not in parsed["env"]


def test_claude_existing_auth_token_wins_and_api_key_is_removed(
    tmp_path: Path,
) -> None:
    adapter = claude_adapter(tmp_path)
    content = json.dumps(
        {
            "env": {
                "ANTHROPIC_BASE_URL": "https://old.example.com",
                "ANTHROPIC_AUTH_TOKEN": "old-auth-token",
                "ANTHROPIC_API_KEY": "old-api-key",
            }
        }
    ).encode()
    plan = claude_plan(adapter, content)
    target = plan_file(plan, adapter.managed_paths[0])

    rendered = adapter.render(target, content)
    parsed = json.loads(rendered)
    assert parsed["env"]["ANTHROPIC_AUTH_TOKEN"] == CLAUDE_SECRET
    assert "ANTHROPIC_API_KEY" not in parsed["env"]


def test_claude_existing_api_key_is_preserved_as_credential_slot(
    tmp_path: Path,
) -> None:
    adapter = claude_adapter(tmp_path)
    content = json.dumps(
        {
            "env": {
                "ANTHROPIC_BASE_URL": "https://old.example.com",
                "ANTHROPIC_API_KEY": "old-api-key",
            }
        }
    ).encode()
    plan = claude_plan(adapter, content)
    target = plan_file(plan, adapter.managed_paths[0])

    parsed = json.loads(adapter.render(target, content))
    assert parsed["env"]["ANTHROPIC_API_KEY"] == CLAUDE_SECRET
    assert "ANTHROPIC_AUTH_TOKEN" not in parsed["env"]


def test_claude_env_model_shadows_top_level_model(tmp_path: Path) -> None:
    adapter = claude_adapter(tmp_path)
    content = json.dumps(
        {
            "model": "top-level-model",
            "env": {
                "ANTHROPIC_BASE_URL": "https://old.example.com",
                "ANTHROPIC_MODEL": "env-model",
            },
        }
    ).encode()
    plan = claude_plan(adapter, content)
    target = plan_file(plan, adapter.managed_paths[0])

    parsed = json.loads(adapter.render(target, content))
    assert parsed["env"]["ANTHROPIC_MODEL"] == NEW_MODEL
    assert parsed["model"] == "top-level-model"
    assert [warning.code for warning in plan.warnings] == ["MODEL_SHADOWED"]


def test_claude_top_level_model_is_updated_when_env_model_absent(
    tmp_path: Path,
) -> None:
    adapter = claude_adapter(tmp_path)
    content = json.dumps(
        {
            "model": "top-level-model",
            "env": {"ANTHROPIC_BASE_URL": "https://old.example.com"},
        }
    ).encode()
    plan = claude_plan(adapter, content)
    target = plan_file(plan, adapter.managed_paths[0])

    parsed = json.loads(adapter.render(target, content))
    assert parsed["model"] == NEW_MODEL
    assert "ANTHROPIC_MODEL" not in parsed["env"]
    assert plan.warnings == []


def test_claude_missing_secret_keeps_existing_credentials(tmp_path: Path) -> None:
    adapter = claude_adapter(tmp_path)
    plan = claude_plan(adapter, CLAUDE_BYTES, secret=None)
    target = plan_file(plan, adapter.managed_paths[0])

    rendered = adapter.render(target, CLAUDE_BYTES)
    parsed = json.loads(rendered.decode("utf-8-sig"))
    assert parsed["env"]["ANTHROPIC_AUTH_TOKEN"] == "old-token-1234567890"
    assert [warning.code for warning in plan.warnings] == ["PROFILE_SECRET_EMPTY"]


def test_claude_changes_never_contain_plaintext_secret(tmp_path: Path) -> None:
    adapter = claude_adapter(tmp_path)
    plan = claude_plan(adapter, CLAUDE_BYTES)
    target = plan_file(plan, adapter.managed_paths[0])

    dumped = json.dumps(
        [change.model_dump() for change in target.changes],
        ensure_ascii=False,
    )
    assert CLAUDE_SECRET not in dumped
    secret_change = next(
        change for change in target.changes if change.field == "env.ANTHROPIC_AUTH_TOKEN"
    )
    assert secret_change.before is not None
    assert secret_change.after is not None
    assert secret_change.after != CLAUDE_SECRET


# ---------------------------------------------------------------------------
# Codex CLI 映射
# ---------------------------------------------------------------------------


def test_codex_missing_files_create_config_and_auth(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)
    plan = codex_plan(adapter, None, None)
    config_path, auth_path = adapter.managed_paths

    assert plan.blockers == []
    config_plan = plan_file(plan, config_path)
    auth_plan = plan_file(plan, auth_path)
    assert config_plan.create is True
    assert auth_plan.create is True

    rendered_config = adapter.render(config_plan, b"")
    rendered_auth = adapter.render(auth_plan, b"")
    adapter.verify(config_plan, b"", rendered_config)
    adapter.verify(auth_plan, b"", rendered_auth)

    assert 'model = "contract-new-model"' in rendered_config.decode()
    assert 'model_provider = "openai"' in rendered_config.decode()
    assert 'wire_api = "chat"' in rendered_config.decode()
    assert json.loads(rendered_auth) == {"OPENAI_API_KEY": CODEX_SECRET}
    assert "重启" in plan.restart_message


def test_codex_official_host_uses_responses_wire_api(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)
    plan = codex_plan(
        adapter,
        None,
        None,
        base_url="https://api.openai.com/v1",
    )
    config_plan = plan_file(plan, adapter.managed_paths[0])

    assert 'wire_api = "responses"' in adapter.render(config_plan, b"").decode()


def test_codex_preserves_auth_oauth_fields_and_warns(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)
    plan = codex_plan(adapter, CODEX_CONFIG, CODEX_AUTH)
    _, auth_path = adapter.managed_paths
    auth_plan = plan_file(plan, auth_path)
    original_auth = json.dumps(CODEX_AUTH).encode()

    rendered = adapter.render(auth_plan, original_auth)
    adapter.verify(auth_plan, original_auth, rendered)
    parsed = json.loads(rendered)
    assert parsed["OPENAI_API_KEY"] == CODEX_SECRET
    assert parsed["tokens"] == CODEX_AUTH["tokens"]
    assert parsed["last_refresh"] == CODEX_AUTH["last_refresh"]
    assert [warning.code for warning in plan.warnings] == ["OAUTH_AUTH_PRESENT"]


def test_codex_missing_secret_leaves_auth_untouched(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)
    plan = codex_plan(adapter, CODEX_CONFIG, CODEX_AUTH, secret=None)

    assert [item.path for item in plan.files] == [str(adapter.managed_paths[0])]
    assert [warning.code for warning in plan.warnings] == ["PROFILE_SECRET_EMPTY"]


def test_codex_env_key_conflict_blocks_config_plan(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)
    config = (
        'model_provider = "openai"\n'
        "\n"
        "[model_providers.openai]\n"
        'name = "OpenAI"\n'
        'env_key = "CUSTOM_OPENAI_KEY"\n'
    )

    plan = codex_plan(adapter, config, None)

    assert [blocker.code for blocker in plan.blockers] == ["ENV_KEY_CONFLICT"]
    assert str(adapter.managed_paths[0]) not in [item.path for item in plan.files]


def test_codex_matching_env_key_is_accepted(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)
    config = (
        'model_provider = "openai"\n'
        "\n"
        "[model_providers.openai]\n"
        'name = "OpenAI"\n'
        'env_key = "OPENAI_API_KEY"\n'
    )

    plan = codex_plan(adapter, config, None)

    assert plan.blockers == []
    config_plan = plan_file(plan, adapter.managed_paths[0])
    assert any(edit.path == ["model_providers", "openai", "base_url"] for edit in config_plan.edits)


def test_codex_without_selected_model_keeps_existing_model(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)
    plan = codex_plan(adapter, CODEX_CONFIG, CODEX_AUTH, model=None)
    config_plan = plan_file(plan, adapter.managed_paths[0])

    assert all(edit.path != ["model"] for edit in config_plan.edits)
    rendered = adapter.render(config_plan, CODEX_CONFIG)
    assert 'model = "gpt-old"' in rendered.decode()


def test_codex_malformed_auth_is_a_blocker_even_with_secret(
    tmp_path: Path,
) -> None:
    adapter = codex_adapter(tmp_path)
    _, auth_path = adapter.managed_paths
    # 替换为损坏的 auth 字节, 保留 config 正常。
    current = codex_current(adapter, CODEX_CONFIG, None)
    current[str(auth_path)] = ToolCurrentFile(
        path=str(auth_path),
        exists=True,
        data=b'{"tokens": ',
    )
    profile = make_profile(
        "Codex 档案",
        protocol="openai",
        base_url="https://relay.example.com/v1",
    )

    corrupted = adapter.plan(
        profile,
        secret=CODEX_SECRET,
        model=NEW_MODEL,
        current=current,
    )

    auth_blockers = [item for item in corrupted.blockers if item.path == str(auth_path)]
    assert [blocker.code for blocker in auth_blockers] == ["PARSE_ERROR"]
    assert str(auth_path) not in [item.path for item in corrupted.files]


def test_codex_changes_never_contain_plaintext_secret(tmp_path: Path) -> None:
    adapter = codex_adapter(tmp_path)
    plan = codex_plan(adapter, CODEX_CONFIG, CODEX_AUTH)
    auth_plan = plan_file(plan, adapter.managed_paths[1])

    dumped = json.dumps(
        [change.model_dump() for change in auth_plan.changes],
        ensure_ascii=False,
    )
    assert CODEX_SECRET not in dumped
