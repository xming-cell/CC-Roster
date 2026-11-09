"""最小只读适配器, 仅用于验证共享契约测试本身; 不是生产适配器。"""

import json
from datetime import UTC, datetime
from pathlib import Path

from app.adapters.base import ToolCapabilities, ToolDetection, ToolReadResult, ToolWarning
from app.core.redaction import redact_secret

_MANAGED_KEYS = ("provider", "base_url", "model", "secret")


def _as_str(value: object) -> str | None:
    return value if isinstance(value, str) else None


class ProbeAdapter:
    id = "probe-tool"
    display_name = "Probe Tool"
    capabilities = ToolCapabilities()

    def __init__(self, config_dir: Path) -> None:
        self._config_dir = config_dir
        self._config_file = config_dir / "settings.json"

    @property
    def managed_paths(self) -> tuple[Path, ...]:
        return (self._config_file,)

    def detect(self) -> ToolDetection:
        values, warnings = self._load()
        return ToolDetection(
            installed=True,
            configured=any(key in values for key in _MANAGED_KEYS),
            config_path=str(self._config_file),
            last_modified=self._last_modified(),
            warnings=warnings,
        )

    def read(self) -> ToolReadResult:
        values, warnings = self._load()
        secret = values.get("secret")
        has_secret = isinstance(secret, str) and bool(secret)
        return ToolReadResult(
            provider=_as_str(values.get("provider")),
            base_url=_as_str(values.get("base_url")),
            model=_as_str(values.get("model")),
            has_secret=has_secret,
            secret_preview=redact_secret(secret) if has_secret else None,
            warnings=warnings,
        )

    def _load(self) -> tuple[dict[str, object], list[ToolWarning]]:
        if not self._config_file.exists():
            return {}, []
        try:
            text = self._config_file.read_text(encoding="utf-8")
        except PermissionError:
            return {}, [
                ToolWarning(
                    code="PERMISSION_DENIED",
                    message=f"无权限读取 {self._config_file.name}",
                )
            ]
        except OSError as exc:
            return {}, [ToolWarning(code="PARSE_ERROR", message=f"读取失败: {type(exc).__name__}")]
        if not text.strip():
            return {}, [
                ToolWarning(code="CONFIG_EMPTY", message=f"{self._config_file.name} 是空文件")
            ]
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            return {}, [
                ToolWarning(
                    code="PARSE_ERROR",
                    message=(
                        f"{self._config_file.name} 第 {exc.lineno} 行第 {exc.colno} 列格式错误"
                    ),
                )
            ]
        if not isinstance(data, dict):
            return {}, [ToolWarning(code="UNKNOWN_FORMAT", message="顶层不是对象")]
        if not any(key in data for key in _MANAGED_KEYS):
            return {}, [ToolWarning(code="UNKNOWN_FORMAT", message="未识别到托管字段")]
        for key in _MANAGED_KEYS:
            value = data.get(key)
            if value is not None and not isinstance(value, str):
                return {}, [ToolWarning(code="UNKNOWN_FORMAT", message=f"{key} 的类型不是字符串")]
        return data, []

    def _last_modified(self) -> datetime | None:
        try:
            return datetime.fromtimestamp(self._config_file.stat().st_mtime, tz=UTC)
        except OSError:
            return None
