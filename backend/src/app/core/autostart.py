"""开机自启: Windows 注册表 / macOS LaunchAgent / Linux .desktop。

默认关闭; 只有用户显式开启才写系统项, 撤销时删除。
"""

from __future__ import annotations

import plistlib
import shlex
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol


class AutostartError(RuntimeError):
    """系统项写入 / 删除失败。"""


class AutostartBackend(Protocol):
    def is_enabled(self) -> bool: ...

    def enable(self, command: str) -> None: ...

    def disable(self) -> None: ...


def default_command() -> str:
    return f'"{sys.executable}" -m app.desktop'


class WindowsRunBackend:
    _KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    _NAME = "CC-Roster"

    def is_enabled(self) -> bool:
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self._KEY) as key:
                winreg.QueryValueEx(key, self._NAME)
        except FileNotFoundError:
            return False
        except OSError:
            return False
        return True

    def enable(self, command: str) -> None:
        import winreg

        try:
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, self._KEY) as key:
                winreg.SetValueEx(key, self._NAME, 0, winreg.REG_SZ, command)
        except OSError as exc:
            raise AutostartError(f"注册表写入失败: {exc}") from exc

    def disable(self) -> None:
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, self._KEY, 0, winreg.KEY_SET_VALUE
            ) as key:
                winreg.DeleteValue(key, self._NAME)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise AutostartError(f"注册表清理失败: {exc}") from exc


class FileAutostartBackend:
    def __init__(self, path: Path, *, platform: str) -> None:
        self._path = path
        self._platform = platform

    @property
    def path(self) -> Path:
        return self._path

    def is_enabled(self) -> bool:
        return self._path.is_file()

    def enable(self, command: str) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if self._platform == "darwin":
                payload = {
                    "Label": "com.ccroster.app",
                    "ProgramArguments": _command_arguments(command),
                    "RunAtLoad": True,
                }
                self._path.write_bytes(plistlib.dumps(payload))
            elif self._platform.startswith("linux"):
                self._path.write_text(
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    "Name=CC-Roster\n"
                    f"Exec={command}\n"
                    "X-GNOME-Autostart-enabled=true\n",
                    encoding="utf-8",
                )
            else:
                raise AutostartError(f"当前平台不支持自启: {self._platform}")
        except OSError as exc:
            raise AutostartError(f"自启文件写入失败: {exc}") from exc

    def disable(self) -> None:
        try:
            self._path.unlink(missing_ok=True)
        except OSError as exc:
            raise AutostartError(f"自启文件清理失败: {exc}") from exc


class AutostartManager:
    def __init__(self, backend: AutostartBackend, *, command: str | None = None) -> None:
        self._backend = backend
        self._command = command or default_command()

    def is_enabled(self) -> bool:
        return self._backend.is_enabled()

    def set_enabled(self, enabled: bool) -> None:
        if enabled:
            self._backend.enable(self._command)
        else:
            self._backend.disable()


def build_autostart_manager(
    *,
    platform: str | None = None,
    home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> AutostartManager:
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else home
    environ = {} if environ is None else environ
    if platform == "win32":
        return AutostartManager(WindowsRunBackend())
    if platform == "darwin":
        return AutostartManager(
            FileAutostartBackend(
                home / "Library" / "LaunchAgents" / "com.ccroster.app.plist", platform=platform
            )
        )
    if platform.startswith("linux"):
        base = (
            Path(environ.get("XDG_CONFIG_HOME", ""))
            if environ.get("XDG_CONFIG_HOME")
            else home / ".config"
        )
        return AutostartManager(
            FileAutostartBackend(base / "autostart" / "cc-roster.desktop", platform=platform)
        )
    raise AutostartError(f"当前平台不支持自启: {platform}")


def _command_arguments(command: str) -> list[str]:
    return [part.strip('"') for part in shlex.split(command, posix=False)]
