"""020 Gemini CLI / OpenCode 适配器与能力矩阵。"""

import json
from pathlib import Path

from profile_fixtures import make_profile

from app.adapters.base import ToolCapabilities, ToolCurrentFile
from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.gemini_cli import GeminiCliAdapter
from app.adapters.opencode import OpenCodeAdapter
from app.adapters.registry import ToolRegistry
from app.services.tool_discovery import ToolDiscoveryService


def gemini_adapter(tmp_path: Path, environ: dict[str, str] | None = None) -> GeminiCliAdapter:
    return GeminiCliAdapter(
        tmp_path / "gemini",
        which=lambda _name: None,
        environ=environ or {},
    )


def opencode_adapter(tmp_path: Path, environ: dict[str, str] | None = None) -> OpenCodeAdapter:
    return OpenCodeAdapter(
        tmp_path / "opencode",
        which=lambda _name: None,
        environ=environ or {},
    )


def test_gemini_reads_model_base_url_and_reports_environment_secret(tmp_path: Path) -> None:
    config_dir = tmp_path / "gemini"
    config_dir.mkdir()
    (config_dir / "settings.json").write_text(
        json.dumps({"model": "gemini-2.5-pro", "baseUrl": "https://gemini.example/v1"}),
        encoding="utf-8",
    )
    adapter = gemini_adapter(tmp_path, {"GEMINI_API_KEY": "secret"})

    detection = adapter.detect()
    read = adapter.read()

    assert detection.installed is True
    assert detection.configured is True
    assert read.model == "gemini-2.5-pro"
    assert read.base_url == "https://gemini.example/v1"
    assert read.has_secret is True
    assert any(warning.code == "SECRET_IN_ENV" for warning in read.warnings)
    assert adapter.capabilities.sessions is False
    assert adapter.capabilities.launch is True
    assert adapter.capabilities.write is True


def test_gemini_plan_renders_model_and_base_url_and_preserves_unknown_fields(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "gemini"
    config_dir.mkdir()
    original = b'{"theme":"dark","model":"old","baseUrl":"https://old.example"}'
    (config_dir / "settings.json").write_bytes(original)
    adapter = gemini_adapter(tmp_path)
    profile = make_profile(
        protocol="openai",
        base_url="https://new.example/v1",
        models=[{"id": "gemini-2.5-pro"}],
    )
    plan = adapter.plan(
        profile,
        secret="sk-secret",
        model="gemini-2.5-pro",
        current={
            str(config_dir / "settings.json"): ToolCurrentFile(
                path=str(config_dir / "settings.json"),
                exists=True,
                data=original,
            )
        },
    )

    assert len(plan.files) == 1
    rendered = adapter.render(plan.files[0], original)
    adapter.verify(plan.files[0], original, rendered)
    body = json.loads(rendered)
    assert body["model"] == "gemini-2.5-pro"
    assert body["baseUrl"] == "https://new.example/v1"
    assert body["theme"] == "dark"
    assert any(warning.code == "SECRET_ENV_ONLY" for warning in plan.warnings)


def test_opencode_reads_nested_provider_url_and_plans_nested_edit(tmp_path: Path) -> None:
    config_dir = tmp_path / "opencode"
    config_dir.mkdir()
    original = json.dumps(
        {
            "model": "openai/gpt-5",
            "provider": {"openai": {"options": {"baseURL": "https://old.example/v1"}}},
            "theme": "system",
        }
    ).encode()
    (config_dir / "opencode.json").write_bytes(original)
    adapter = opencode_adapter(tmp_path)
    read = adapter.read()
    profile = make_profile(
        protocol="openai",
        base_url="https://new.example/v1",
        models=[{"id": "openai/gpt-5"}],
    )
    plan = adapter.plan(
        profile,
        secret=None,
        model="openai/gpt-5",
        current={
            str(config_dir / "opencode.json"): ToolCurrentFile(
                path=str(config_dir / "opencode.json"),
                exists=True,
                data=original,
            )
        },
    )

    assert read.model == "openai/gpt-5"
    assert read.base_url == "https://old.example/v1"
    rendered = adapter.render(plan.files[0], original)
    adapter.verify(plan.files[0], original, rendered)
    body = json.loads(rendered)
    assert body["provider"]["openai"]["options"]["baseURL"] == "https://new.example/v1"
    assert body["theme"] == "system"
    assert any(warning.code == "PROFILE_SECRET_EMPTY" for warning in plan.warnings)


def test_existing_adapters_keep_behaviour_with_new_registry(tmp_path: Path) -> None:
    registry = ToolRegistry(
        [
            ClaudeCodeAdapter(tmp_path / "claude", which=lambda _name: None),
            CodexCliAdapter(tmp_path / "codex", which=lambda _name: None),
            gemini_adapter(tmp_path),
            opencode_adapter(tmp_path),
        ]
    )
    service = ToolDiscoveryService(registry)

    response = service.list_tools()

    assert [tool.id for tool in response.tools] == []
    assert registry.get("claude-code").id == "claude-code"
    assert isinstance(registry.get("gemini-cli").capabilities, ToolCapabilities)
