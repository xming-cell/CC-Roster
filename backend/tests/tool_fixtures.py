"""工具发现测试共享的 fixture 种子与最小适配器替身。

不是 pytest 插件, 也不会被收集; 供 `test_tool_discovery` / `test_tool_secrets` /
`test_tools_api` 复用同一份目录结构, 避免每个文件复制 setup。
"""

import json
from pathlib import Path

from app.adapters.base import (
    ToolAdapter,
    ToolCapabilities,
    ToolDetection,
    ToolReadResult,
    ToolWarning,
)
from app.adapters.claude_code import ClaudeCodeAdapter
from app.adapters.codex_cli import CodexCliAdapter
from app.adapters.registry import ToolRegistry
from app.services.tool_discovery import ToolDiscoveryService

CLAUDE_TOKEN = "sk-ant-1234567890abcdef"
CODEX_KEY = "sk-openai-1234567890abcdef"

CODEX_CONFIG = """\
model = "gpt-5-codex"
model_provider = "openai"

[model_providers.openai]
name = "OpenAI"
base_url = "https://api.openai.com/v1"
wire_api = "responses"
"""


class StubAdapter:
    """最小适配器替身: 用于固定「未安装 / 抛异常」这类服务层行为。"""

    capabilities = ToolCapabilities()

    def __init__(
        self,
        adapter_id: str,
        *,
        detection: ToolDetection | None = None,
        result: ToolReadResult | None = None,
        error: Exception | None = None,
        error_stage: str = "detect",
    ) -> None:
        self.id = adapter_id
        self.display_name = adapter_id
        self.managed_paths: tuple[Path, ...] = ()
        self._detection = detection or ToolDetection(installed=True, configured=False)
        self._result = result or ToolReadResult()
        self._error = error
        self._error_stage = error_stage

    def detect(self) -> ToolDetection:
        if self._error is not None and self._error_stage == "detect":
            raise self._error
        return self._detection

    def read(self) -> ToolReadResult:
        if self._error is not None and self._error_stage == "read":
            raise self._error
        return self._result


def claude_adapter(config_dir: Path) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(config_dir, which=lambda _name: None)


def codex_adapter(config_dir: Path) -> CodexCliAdapter:
    return CodexCliAdapter(config_dir, which=lambda _name: None)


def make_service(*adapters: ToolAdapter) -> ToolDiscoveryService:
    return ToolDiscoveryService(ToolRegistry(adapters))


def write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def seed_claude(config_dir: Path, *, model: str = "claude-sonnet-4") -> Path:
    path = config_dir / "settings.json"
    write_json(
        path,
        {
            "model": model,
            "env": {
                "ANTHROPIC_BASE_URL": "https://api.anthropic.com",
                "ANTHROPIC_AUTH_TOKEN": CLAUDE_TOKEN,
            },
        },
    )
    return path


def seed_codex(config_dir: Path) -> None:
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.toml").write_text(CODEX_CONFIG, encoding="utf-8")
    write_json(config_dir / "auth.json", {"OPENAI_API_KEY": CODEX_KEY})


def warning_codes(tool_warnings: list[ToolWarning]) -> list[str]:
    return [warning.code for warning in tool_warnings]
