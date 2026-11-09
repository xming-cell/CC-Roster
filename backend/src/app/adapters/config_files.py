"""适配器共享的只读文件工具。

这里只做三件事: 解析配置目录、容错读取文本、把失败归一成 `ToolWarning`。
所有函数都不写盘; 解析失败只返回 warning, 由适配器决定如何降级。
"""

import json
import re
import tomllib
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from app.adapters.base import ToolWarning, WarningCode

WhichFn = Callable[[str], str | None]

SUPPORTED_SCHEMA_VERSION = 1

_TOML_POSITION = re.compile(r"at line (\d+), column (\d+)")


def make_warning(code: WarningCode, message: str) -> ToolWarning:
    """warning 的 code 是稳定契约, message 只给人看。"""
    return ToolWarning(code=code, message=message)


def resolve_config_dir(
    *,
    environ: Mapping[str, str],
    home: Path,
    env_var: str,
    default_name: str,
) -> Path:
    """按环境变量定位配置目录: 空串回退默认, 相对路径按注入的 home 解析。"""
    raw = environ.get(env_var, "").strip()
    if not raw:
        return home / default_name
    candidate = Path(raw)
    return candidate if candidate.is_absolute() else home / candidate


def read_text(path: Path) -> tuple[str | None, list[ToolWarning]]:
    """读取 UTF-8 文本; 文件缺失返回 `(None, [])`, 其余失败返回 warning。"""
    try:
        return path.read_text(encoding="utf-8-sig"), []
    except (FileNotFoundError, NotADirectoryError):
        return None, []
    except PermissionError:
        return None, [make_warning("PERMISSION_DENIED", f"无权限读取 {path.name}")]
    except UnicodeDecodeError:
        return None, [make_warning("PARSE_ERROR", f"{path.name} 不是有效的 UTF-8 文本")]
    except OSError as exc:
        return None, [make_warning("PARSE_ERROR", f"读取 {path.name} 失败: {type(exc).__name__}")]


def load_json_object(
    path: Path, *, warn_on_empty: bool
) -> tuple[dict[str, object] | None, list[ToolWarning]]:
    """读取 JSON 对象; 语法错误只回显行 / 列, 绝不回显文件内容。"""
    text, warnings = read_text(path)
    if warnings or text is None:
        return None, warnings
    if not text.strip():
        return None, _empty_warnings(path, warn_on_empty)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return None, [
            make_warning("PARSE_ERROR", f"{path.name} 第 {exc.lineno} 行第 {exc.colno} 列格式错误")
        ]
    if not isinstance(data, dict):
        return None, [make_warning("UNKNOWN_FORMAT", f"{path.name} 顶层不是对象")]
    return data, []


def load_toml_object(
    path: Path, *, warn_on_empty: bool
) -> tuple[dict[str, object] | None, list[ToolWarning]]:
    """读取 TOML 表; 语法错误只回显行 / 列, 绝不回显文件内容。"""
    text, warnings = read_text(path)
    if warnings or text is None:
        return None, warnings
    if not text.strip():
        return None, _empty_warnings(path, warn_on_empty)
    try:
        return tomllib.loads(text), []
    except tomllib.TOMLDecodeError as exc:
        line, column = _toml_position(exc, text)
        return None, [
            make_warning("PARSE_ERROR", f"{path.name} 第 {line} 行第 {column} 列格式错误")
        ]


def string_field(
    container: Mapping[str, object],
    key: str,
    label: str,
    warnings: list[ToolWarning],
) -> str | None:
    """取字符串字段; 类型不符时记 `UNKNOWN_FORMAT`, 不强制转换。"""
    if key not in container:
        return None
    value = container[key]
    if not isinstance(value, str):
        warnings.append(make_warning("UNKNOWN_FORMAT", f"{label} 的类型不是字符串"))
        return None
    return value.strip() or None


def table_field(
    container: Mapping[str, object],
    key: str,
    label: str,
    warnings: list[ToolWarning],
) -> dict[str, object] | None:
    """取对象 / 表字段; 类型不符时记 `UNKNOWN_FORMAT`。"""
    if key not in container:
        return None
    value = container[key]
    if not isinstance(value, dict):
        warnings.append(make_warning("UNKNOWN_FORMAT", f"{label} 不是对象"))
        return None
    return value


def schema_version_supported(data: Mapping[str, object]) -> bool:
    """只支持 `schema_version = 1`; 缺失版本按当前格式处理。"""
    if "schema_version" not in data:
        return True
    version = data["schema_version"]
    return (
        isinstance(version, int)
        and not isinstance(version, bool)
        and version == SUPPORTED_SCHEMA_VERSION
    )


def file_last_modified(path: Path) -> datetime | None:
    """返回带 UTC 时区的 mtime; 文件不存在或无权限时返回 None。"""
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def is_third_party_base_url(base_url: str | None, official_host: str) -> bool | None:
    """按 host 判定第三方中转; 无 base_url 视为官方, host 无法解析时返回 None。"""
    if base_url is None:
        return False
    host = _host_of(base_url)
    if host is None:
        return None
    return host != official_host.lower()


def _host_of(base_url: str) -> str | None:
    value = base_url.strip()
    if not value:
        return None
    candidate = value if "://" in value else f"//{value}"
    host = urlsplit(candidate).hostname
    return host.lower() if host else None


def _empty_warnings(path: Path, warn_on_empty: bool) -> list[ToolWarning]:
    return [make_warning("CONFIG_EMPTY", f"{path.name} 是空文件")] if warn_on_empty else []


def _toml_position(exc: tomllib.TOMLDecodeError, text: str) -> tuple[int, int]:
    """tomllib 3.12 不暴露位置属性; 优先解析消息, 否则按文件末尾折算。"""
    match = _TOML_POSITION.search(str(exc))
    if match:
        return int(match.group(1)), int(match.group(2))
    lines = text.splitlines() or [""]
    return len(lines), len(lines[-1]) + 1
