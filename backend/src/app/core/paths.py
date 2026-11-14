"""数据目录解析与创建, 规则见 `docs/decisions.md` 的 ADR-007。

解析函数只做纯字符串 / 路径计算, 不触碰文件系统; 创建目录由 `ensure_data_dirs` 负责。
测试通过注入 `platform` / `environ` / `home` 覆盖三个平台分支, 不依赖运行平台。
"""

import os
import sys
from collections.abc import Mapping
from pathlib import Path, PurePath, PurePosixPath, PureWindowsPath

_WINDOWS_APP_DIR = "CC-Roster"
_MACOS_APP_DIR = "CC-Roster"
_LINUX_APP_DIR = "cc-roster"
_DATA_SUBDIRS = ("db", "logs")


def resolve_data_dir(
    *,
    platform: str | None = None,
    environ: Mapping[str, str] | None = None,
    home: PurePath | None = None,
) -> PurePath:
    """按 ADR-007 返回数据根目录。

    - Windows: `%LOCALAPPDATA%\\CC-Roster`; 未设置时回退到 `<home>\\AppData\\Local\\CC-Roster`。
    - macOS: `~/Library/Application Support/CC-Roster`。
    - Linux: `${XDG_DATA_HOME:-$HOME/.local/share}/cc-roster`。
    - 未知平台明确报错, 不猜测目录。
    """
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else home

    if platform == "win32":
        local_app_data = environ.get("LOCALAPPDATA")
        windows_base = (
            PureWindowsPath(local_app_data)
            if local_app_data
            else PureWindowsPath(home) / "AppData" / "Local"
        )
        return windows_base / _WINDOWS_APP_DIR

    if platform == "darwin":
        macos_base = PurePosixPath(home) / "Library" / "Application Support"
        return macos_base / _MACOS_APP_DIR

    if platform == "linux":
        xdg_data_home = environ.get("XDG_DATA_HOME")
        if xdg_data_home and PurePosixPath(xdg_data_home).is_absolute():
            linux_base = PurePosixPath(xdg_data_home)
        else:
            linux_base = PurePosixPath(home) / ".local" / "share"
        return linux_base / _LINUX_APP_DIR

    raise ValueError(f"unsupported platform: {platform!r}")


def ensure_data_dirs(data_dir: PurePath) -> Path:
    """创建数据根目录及 `db/`、`logs/`; 已存在时幂等, 并返回真实路径。"""
    root = Path(data_dir)
    root.mkdir(parents=True, exist_ok=True)
    for name in _DATA_SUBDIRS:
        (root / name).mkdir(exist_ok=True)
    return root


def validate_absolute_path(value: str, *, label: str = "路径") -> str:
    """校验绝对路径字符串, 拒绝相对路径与 `..` 段; 不触碰文件系统。"""
    path = Path(value)
    if not path.is_absolute():
        raise ValueError(f"{label}必须是绝对路径")
    if ".." in path.parts:
        raise ValueError(f"{label}不能包含 .. 段")
    return str(path)


def resolve_absolute_path(path: Path, *, label: str = "路径") -> Path:
    """校验并解析绝对路径的 symlink; 目标文件可以不存在。"""
    value = validate_absolute_path(str(path), label=label)
    return Path(value).resolve(strict=False)
