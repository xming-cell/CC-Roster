"""Codex CLI 只读适配器。

读取 `config.toml` 的模型 / provider 与 `auth.json` 的 `OPENAI_API_KEY`。
`env_key` 只提示密钥在环境变量中, 本应用绝不读取对应变量; `auth.json` 里的
OAuth token 也不解析。
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
    load_toml_object,
    make_warning,
    resolve_config_dir,
    schema_version_supported,
    string_field,
    table_field,
)
from app.core.redaction import redact_secret, redact_text

_ID = "codex-cli"
_DISPLAY_NAME = "Codex CLI"
_ENV_VAR = "CODEX_HOME"
_DEFAULT_DIR = ".codex"
_CONFIG_FILE_NAME = "config.toml"
_AUTH_FILE_NAME = "auth.json"
_EXECUTABLE = "codex"
_OFFICIAL_PROVIDER = "openai"
_OFFICIAL_HOST = "api.openai.com"
_OPENAI_DISPLAY_NAME = "OpenAI"
_KNOWN_WIRE_APIS = frozenset({"chat", "responses"})


def resolve_codex_config_dir(*, environ: Mapping[str, str], home: Path) -> Path:
    """`CODEX_HOME` 优先, 空串回退 `~/.codex`。"""
    return resolve_config_dir(
        environ=environ,
        home=home,
        env_var=_ENV_VAR,
        default_name=_DEFAULT_DIR,
    )


@dataclass(frozen=True, slots=True)
class _CodexConfig:
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    is_third_party: bool | None = None
    has_secret: bool = False
    secret_preview: str | None = None
    configured: bool = False


class CodexCliAdapter:
    id = _ID
    display_name = _DISPLAY_NAME
    capabilities = ToolCapabilities()

    def __init__(self, config_dir: Path, *, which: WhichFn | None = None) -> None:
        self._config_dir = config_dir
        self._config_file = config_dir / _CONFIG_FILE_NAME
        self._auth_file = config_dir / _AUTH_FILE_NAME
        self._which = shutil.which if which is None else which

    @property
    def managed_paths(self) -> tuple[Path, ...]:
        return (self._config_file, self._auth_file)

    def detect(self) -> ToolDetection:
        config, warnings = self._load()
        return ToolDetection(
            installed=self._is_installed(),
            configured=config.configured,
            config_path=str(self._config_file),
            last_modified=(
                file_last_modified(self._config_file) or file_last_modified(self._auth_file)
            ),
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

    def _load(self) -> tuple[_CodexConfig, list[ToolWarning]]:
        data, warnings = load_toml_object(self._config_file, warn_on_empty=True)
        has_secret, secret_preview = self._read_secret(warnings)
        if data is None:
            return (
                _CodexConfig(
                    has_secret=has_secret,
                    secret_preview=secret_preview,
                    configured=has_secret,
                ),
                warnings,
            )
        if not schema_version_supported(data):
            warnings.append(
                make_warning("UNSUPPORTED_VERSION", "config.toml 的 schema_version 不受支持")
            )
            return (
                _CodexConfig(
                    has_secret=has_secret,
                    secret_preview=secret_preview,
                    configured=has_secret,
                ),
                warnings,
            )

        model = string_field(data, "model", "model", warnings)
        provider_id = string_field(data, "model_provider", "model_provider", warnings)
        providers = table_field(data, "model_providers", "model_providers", warnings)
        entry = self._active_provider(providers, provider_id, warnings)

        provider_name: str | None = None
        base_url: str | None = None
        wire_api: str | None = None
        env_key: str | None = None
        if entry is not None:
            provider_name = string_field(entry, "name", "model_providers.name", warnings)
            base_url = string_field(entry, "base_url", "model_providers.base_url", warnings)
            wire_api = string_field(entry, "wire_api", "model_providers.wire_api", warnings)
            env_key = string_field(entry, "env_key", "model_providers.env_key", warnings)
            if wire_api is not None and wire_api not in _KNOWN_WIRE_APIS:
                warnings.append(
                    make_warning("UNSUPPORTED_VERSION", "model_providers 的 wire_api 不受支持")
                )
            if env_key is not None:
                warnings.append(
                    make_warning(
                        "SECRET_IN_ENV",
                        f"密钥来自环境变量 {redact_text(env_key)}, 本应用不读取",
                    )
                )

        provider = self._provider_display(provider_id, provider_name)
        configured = (
            any(
                value is not None
                for value in (model, provider_id, provider_name, base_url, wire_api, env_key)
            )
            or has_secret
        )
        if not configured and not warnings:
            warnings.append(make_warning("NO_MANAGED_FIELDS", "config.toml 未包含可识别的托管字段"))

        return (
            _CodexConfig(
                provider=provider,
                base_url=base_url,
                model=model,
                is_third_party=self._third_party(provider_id, base_url),
                has_secret=has_secret,
                secret_preview=secret_preview,
                configured=configured,
            ),
            warnings,
        )

    def _read_secret(self, warnings: list[ToolWarning]) -> tuple[bool, str | None]:
        data, auth_warnings = load_json_object(self._auth_file, warn_on_empty=False)
        warnings.extend(auth_warnings)
        if data is None:
            return False, None
        key = string_field(data, "OPENAI_API_KEY", "auth.json 的 OPENAI_API_KEY", warnings)
        if key is None:
            return False, None
        return True, redact_secret(key)

    @staticmethod
    def _active_provider(
        providers: Mapping[str, object] | None,
        provider_id: str | None,
        warnings: list[ToolWarning],
    ) -> Mapping[str, object] | None:
        if provider_id is None:
            return None
        raw_entry = None if providers is None else providers.get(provider_id)
        if raw_entry is None:
            # `openai` 是 Codex 内置 provider, 允许没有同名表。
            if provider_id != _OFFICIAL_PROVIDER:
                warnings.append(
                    make_warning(
                        "UNKNOWN_FORMAT",
                        "model_provider 指向的 provider 未在 model_providers 中定义",
                    )
                )
            return None
        if not isinstance(raw_entry, dict):
            warnings.append(make_warning("UNKNOWN_FORMAT", "model_provider 指向的 provider 不是表"))
            return None
        return raw_entry

    @staticmethod
    def _provider_display(provider_id: str | None, provider_name: str | None) -> str | None:
        if provider_id is None:
            return None
        if provider_name is not None:
            return redact_text(provider_name)
        if provider_id == _OFFICIAL_PROVIDER:
            return _OPENAI_DISPLAY_NAME
        return redact_text(provider_id)

    @staticmethod
    def _third_party(provider_id: str | None, base_url: str | None) -> bool | None:
        if provider_id is None:
            return None
        if provider_id == _OFFICIAL_PROVIDER:
            return is_third_party_base_url(base_url, _OFFICIAL_HOST)
        return True
