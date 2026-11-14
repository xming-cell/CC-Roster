"""全局快捷键校验与注册边界; 实际库不可用时明确降级。"""

from __future__ import annotations

import contextlib
import re
from typing import Protocol

_MODIFIERS = frozenset({"ctrl", "alt", "shift", "meta", "cmd"})
_HOTKEY = re.compile(r"^(?:[a-z0-9]+(?:\+[a-z0-9]+)+)$")
DEFAULT_HOTKEY = "ctrl+alt+c"


class HotkeyError(ValueError):
    """格式非法或注册失败。"""


class HotkeyConflict(HotkeyError):
    """快捷键已被占用。"""


class HotkeyBackend(Protocol):
    def register(self, hotkey: str) -> None: ...

    def unregister(self, hotkey: str) -> None: ...


class InMemoryHotkeyBackend:
    """测试 / 降级替身: 记录已注册快捷键并模拟冲突。"""

    def __init__(self, occupied: set[str] | None = None) -> None:
        self.registered: set[str] = set()
        self.occupied = occupied or set()

    def register(self, hotkey: str) -> None:
        if hotkey in self.occupied or hotkey in self.registered:
            raise HotkeyConflict(f"快捷键已被占用: {hotkey}")
        self.registered.add(hotkey)

    def unregister(self, hotkey: str) -> None:
        self.registered.discard(hotkey)


class HotkeyManager:
    def __init__(self, backend: HotkeyBackend) -> None:
        self._backend = backend
        self._current: str | None = None

    @property
    def current(self) -> str | None:
        return self._current

    def set(self, hotkey: str) -> None:
        normalized = normalize_hotkey(hotkey)
        if normalized == self._current:
            return
        previous = self._current
        if previous is not None:
            self._backend.unregister(previous)
        try:
            self._backend.register(normalized)
        except HotkeyConflict:
            if previous is not None:
                with contextlib.suppress(HotkeyConflict):
                    self._backend.register(previous)
            raise
        self._current = normalized

    def clear(self) -> None:
        if self._current is not None:
            self._backend.unregister(self._current)
            self._current = None


def normalize_hotkey(value: str) -> str:
    normalized = "+".join(part.strip().lower() for part in value.strip().split("+") if part.strip())
    if not normalized or not _HOTKEY.match(normalized):
        raise HotkeyError("快捷键格式应为 ctrl+alt+c 这种形式")
    parts = normalized.split("+")
    if parts[-1] in _MODIFIERS or not any(part in _MODIFIERS for part in parts[:-1]):
        raise HotkeyError("快捷键必须包含修饰键和普通按键")
    return normalized


def desktop_capabilities() -> tuple[bool, bool, bool]:
    import importlib.util
    import sys

    tray = importlib.util.find_spec("pystray") is not None
    hotkey = importlib.util.find_spec("keyboard") is not None
    autostart = (
        sys.platform == "win32" or sys.platform == "darwin" or sys.platform.startswith("linux")
    )
    return tray, hotkey, autostart
