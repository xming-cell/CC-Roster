"""Claude Code 只读适配器。

只读取用户级 `settings.json`; OAuth / 登录凭据与项目级 `.claude/` 一概不碰。
`env.ANTHROPIC_MODEL` 优先于顶层 `model`, 与 Claude Code 的环境变量覆盖语义一致。
"""

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app.adapters.base import ToolCapabilities, ToolDetection, ToolReadResult, ToolWarning
from app.adapters.config_files import (
    WhichFn,
    file_last_modified,
    is_third_party_base_url,
    load_json_object,
    make_warning,
    resolve_config_dir,
    schema_version_supported,
    string_field,
    table_field,
)
from app.core.redaction import redact_secret

_ID = "claude-code"
_DISPLAY_NAME = "Claude Code"
_ENV_VAR = "CLAUDE_CONFIG_DIR"
_DEFAULT_DIR = ".claude"
_CONFIG_FILE_NAME = "settings.json"
_EXECUTABLE = "claude"
_OFFICIAL_HOST = "api.anthropic.com"
_PROVIDER_NAME = "Anthropic"


def resolve_claude_config_dir(*, environ: Mapping[str, str], home: Path) -> Path:
    """`CLAUDE_CONFIG_DIR` 优先, 空串回退 `~/.claude`。"""
    return resolve_config_dir(
        environ=environ,
        home=home,
        env_var=_ENV_VAR,
        default_name=_DEFAULT_DIR,
    )


@dataclass(frozen=True, slots=True)
class _ClaudeConfig:
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    is_third_party: bool | None = None
    has_secret: bool = False
    secret_preview: str | None = None
    configured: bool = False


class ClaudeCodeAdapter:
    id = _ID
    display_name = _DISPLAY_NAME
    capabilities = ToolCapabilities()

    def __init__(self, config_dir: Path, *, which: WhichFn | None = None) -> None:
        self._config_dir = config_dir
        self._config_file = config_dir / _CONFIG_FILE_NAME
        self._which = shutil.which if which is None else which

    @property
    def managed_paths(self) -> tuple[Path, ...]:
        return (self._config_file,)

    def detect(self) -> ToolDetection:
        config, warnings = self._load()
        return ToolDetection(
            installed=self._is_installed(),
            configured=config.configured,
            config_path=str(self._config_file),
            last_modified=file_last_modified(self._config_file),
            warnings=warnings,
        )

    def read(self) -> ToolReadResult:
        config, warnings = self._load()
        return ToolReadResult(
            provider=config.provider,
            base_url=config.base_url,
            model=config.model,
            is_third_party=config.is_third_party,
            has_secret=config.has_secret,
            secret_preview=config.secret_preview,
            warnings=warnings,
        )

    def _is_installed(self) -> bool:
        return self._config_dir.is_dir() or self._which(_EXECUTABLE) is not None

    def _load(self) -> tuple[_ClaudeConfig, list[ToolWarning]]:
        data, warnings = load_json_object(self._config_file, warn_on_empty=True)
        if data is None:
            return _ClaudeConfig(), warnings
        if not schema_version_supported(data):
            warnings.append(
                make_warning("UNSUPPORTED_VERSION", "settings.json 的 schema_version 不受支持")
            )
            return _ClaudeConfig(), warnings

        env = table_field(data, "env", "env", warnings)
        env_values: Mapping[str, object] = {} if env is None else env
        base_url = string_field(
            env_values, "ANTHROPIC_BASE_URL", "env.ANTHROPIC_BASE_URL", warnings
        )
        auth_token = string_field(
            env_values, "ANTHROPIC_AUTH_TOKEN", "env.ANTHROPIC_AUTH_TOKEN", warnings
        )
        api_key = string_field(env_values, "ANTHROPIC_API_KEY", "env.ANTHROPIC_API_KEY", warnings)
        env_model = string_field(env_values, "ANTHROPIC_MODEL", "env.ANTHROPIC_MODEL", warnings)
        top_model = string_field(data, "model", "model", warnings)

        model = env_model or top_model
        secret = auth_token or api_key
        configured = any(value is not None for value in (base_url, model, secret))
        if not configured and not warnings:
            warnings.append(
                make_warning("NO_MANAGED_FIELDS", "settings.json 未包含可识别的托管字段")
            )

        return (
            _ClaudeConfig(
                provider=_PROVIDER_NAME if configured else None,
                base_url=base_url,
                model=model,
                is_third_party=(
                    is_third_party_base_url(base_url, _OFFICIAL_HOST) if configured else None
                ),
                has_secret=secret is not None,
                secret_preview=redact_secret(secret) if secret is not None else None,
                configured=configured,
            ),
            warnings,
        )
