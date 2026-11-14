"""019/020 共用: JSON 配置的简单托管字段适配器。

Gemini CLI / OpenCode 的配置结构不同, 但都只需要托管 `model` 与一个 base URL
字段; 密钥由工具自己的环境变量读取, 本应用只写非敏感字段。
"""

from __future__ import annotations

import shutil
from collections.abc import Callable, Mapping
from pathlib import Path

from app.adapters.base import (
    ToolBlocker,
    ToolCapabilities,
    ToolCurrentFile,
    ToolDetection,
    ToolPlan,
    ToolPlanWarning,
    ToolReadResult,
    ToolWarning,
)
from app.adapters.config_files import (
    file_last_modified,
    load_json_object,
    make_warning,
    schema_version_supported,
)
from app.adapters.managed_fields import (
    ManagedFieldsAdapter,
    PlanBuilder,
    blocker_for_error,
    display_value,
    parse_json_object,
)
from app.adapters.sessions import session_id_is_safe
from app.adapters.usage import UsageScan
from app.core.errors import AppError
from app.schemas.profile import Profile, ProfileProtocol
from app.schemas.session import SessionMessage, SessionSummary


class SimpleJsonAdapter(ManagedFieldsAdapter):
    """只托管 `model` + base URL 的 JSON 配置适配器。"""

    id: str = ""
    display_name: str = ""
    supported_protocols: tuple[ProfileProtocol, ...] = ("openai",)
    executable: str = ""
    config_file_name: str = "settings.json"
    env_key_names: tuple[str, ...] = ()
    provider_name: str = "第三方"
    model_path: tuple[str, ...] = ("model",)
    base_url_path: tuple[str, ...] = ("baseUrl",)
    capabilities = ToolCapabilities(
        write=True, sessions=False, launch=True, write_mode="managed_fields"
    )

    def __init__(
        self,
        config_dir: Path,
        *,
        which: Callable[[str], str | None] | None = shutil.which,
        environ: Mapping[str, str] | None = None,
    ) -> None:
        self._config_dir = config_dir
        self._config_file = config_dir / self.config_file_name
        self._which = which
        self._environ = environ or {}

    @property
    def managed_paths(self) -> tuple[Path, ...]:
        return (self._config_file,)

    def detect(self) -> ToolDetection:
        config, warnings = self._load()
        return ToolDetection(
            installed=self._config_dir.is_dir() or self._executable() is not None,
            configured=config.configured,
            config_path=str(self._config_file),
            last_modified=file_last_modified(self._config_file),
            warnings=warnings,
        )

    def read(self) -> ToolReadResult:
        config, warnings = self._load()
        return ToolReadResult(
            provider=self.provider_name,
            base_url=config.base_url,
            model=config.model,
            is_third_party=None,
            has_secret=config.has_secret,
            secret_preview=None,
            warnings=warnings,
        )

    def plan(
        self,
        profile: Profile,
        *,
        secret: str | None,
        model: str | None,
        current: Mapping[str, ToolCurrentFile],
    ) -> ToolPlan:
        current_file = current[str(self._config_file)]
        try:
            document = parse_json_object(current_file.data)
        except AppError as exc:
            return ToolPlan(
                files=[],
                blockers=[blocker_for_error(exc, current_file.path)],
                warnings=[],
                restart_required=True,
                restart_message=self._restart_message(),
            )
        if not schema_version_supported(document):
            return ToolPlan(
                files=[],
                blockers=[
                    ToolBlocker(
                        code="UNSUPPORTED_VERSION",
                        message=f"{self.config_file_name} 的 schema_version 不受支持",
                        path=current_file.path,
                    )
                ],
                warnings=[],
                restart_required=True,
                restart_message=self._restart_message(),
            )
        builder = PlanBuilder(current_file.path)
        warnings: list[ToolPlanWarning] = []
        before_model = _nested(document, self.model_path)
        model_before_text = display_value(before_model)
        if model is not None:
            builder.set(self.model_path, model, model_before_text)
        before_base = _nested(document, self.base_url_path)
        builder.set(self.base_url_path, profile.base_url, display_value(before_base))
        if model is None:
            warnings.append(ToolPlanWarning(code="NO_MODELS", message="档案没有模型, 保留原模型"))
        if secret is None:
            warnings.append(
                ToolPlanWarning(
                    code="PROFILE_SECRET_EMPTY",
                    message="档案没有密钥, 工具将从自己的环境变量读取",
                )
            )
        else:
            warnings.append(
                ToolPlanWarning(
                    code="SECRET_ENV_ONLY",
                    message="该工具从环境变量读取密钥, 本应用不会把密钥写入配置文件",
                )
            )
        return ToolPlan(
            files=[builder.build("json")],
            warnings=warnings,
            restart_required=True,
            restart_message=self._restart_message(),
        )

    def list_sessions(self) -> list[SessionSummary]:
        return []

    def read_session_messages(
        self, session_id: str, *, offset: int, limit: int
    ) -> tuple[list[SessionMessage], bool, list[ToolWarning]]:
        if not session_id_is_safe(session_id):
            raise FileNotFoundError(session_id)
        raise FileNotFoundError(session_id)

    def usage_scan(self) -> UsageScan:
        return UsageScan((), 0)

    def _executable(self) -> str | None:
        if self._which is None:
            return None
        found = self._which(self.executable)
        return found if found else None

    def _load(self) -> tuple[_SimpleConfig, list[ToolWarning]]:
        data, warnings = load_json_object(self._config_file, warn_on_empty=True)
        if data is None:
            return _SimpleConfig(), warnings
        if not schema_version_supported(data):
            warnings.append(
                make_warning(
                    "UNSUPPORTED_VERSION", f"{self.config_file_name} 的 schema_version 不受支持"
                )
            )
            return _SimpleConfig(), warnings
        model = _read_model(data, self.model_path, warnings)
        base_url = _read_base_url(data, self.base_url_path, warnings)
        has_secret = any(bool(self._environ.get(name)) for name in self.env_key_names)
        if has_secret:
            warnings.append(
                make_warning(
                    "SECRET_IN_ENV",
                    f"密钥来自环境变量 {', '.join(self.env_key_names)}, 本应用不读取",
                )
            )
        configured = model is not None or base_url is not None or has_secret
        if not configured and not warnings:
            warnings.append(make_warning("NO_MANAGED_FIELDS", "配置里没有可识别的托管字段"))
        return _SimpleConfig(
            model=model, base_url=base_url, has_secret=has_secret, configured=configured
        ), warnings

    def _restart_message(self) -> str:
        return f"{self.display_name} 需要重启后才会读取新的配置文件"


class _SimpleConfig:
    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
        has_secret: bool = False,
        configured: bool = False,
    ) -> None:
        self.model = model
        self.base_url = base_url
        self.has_secret = has_secret
        self.configured = configured


def _nested(document: Mapping[str, object], path: tuple[str, ...]) -> object | None:
    current: object = document
    for segment in path:
        if not isinstance(current, Mapping):
            return None
        current = current.get(segment)
    return current


def _read_model(
    document: Mapping[str, object], path: tuple[str, ...], warnings: list[ToolWarning]
) -> str | None:
    value = _nested(document, path)
    if value is None:
        return None
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, Mapping):
        name = value.get("name")
        if isinstance(name, str):
            return name.strip() or None
    warnings.append(make_warning("UNKNOWN_FORMAT", "model 字段不是字符串或含 name 的对象"))
    return None


def _read_base_url(
    document: Mapping[str, object], path: tuple[str, ...], warnings: list[ToolWarning]
) -> str | None:
    value = _nested(document, path)
    if value is None:
        for legacy in ("base_url", "apiBaseUrl", "baseURL"):
            candidate = document.get(legacy)
            if isinstance(candidate, str) and candidate.strip():
                return candidate.strip()
        return None
    if isinstance(value, str):
        return value.strip() or None
    warnings.append(make_warning("UNKNOWN_FORMAT", "base URL 字段不是字符串"))
    return None
