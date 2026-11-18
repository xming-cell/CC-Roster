"""托盘与全局快捷键的实际实现; 依赖缺失时由调用方降级。"""

from __future__ import annotations

import importlib
import threading
from collections.abc import Callable
from typing import Protocol


class TrayHandle(Protocol):
    def stop(self) -> None: ...


def build_tray(window: object) -> TrayHandle | None:
    try:
        pystray = importlib.import_module("pystray")
        image_module = importlib.import_module("PIL.Image")
        draw_module = importlib.import_module("PIL.ImageDraw")
    except ImportError:
        return None

    image = image_module.new("RGB", (64, 64), "#4f7cff")
    draw = draw_module.Draw(image)
    draw.rectangle((16, 16, 48, 48), fill="#ffffff")
    menu = pystray.Menu(
        pystray.MenuItem("显示", lambda: _show(window), default=True),
        pystray.MenuItem("隐藏", lambda: _hide(window)),
        pystray.MenuItem("退出", lambda: _quit(window)),
    )
    icon = pystray.Icon("cc-roster", image, "CC-Roster", menu)
    thread = threading.Thread(target=icon.run, name="cc-roster-tray", daemon=True)
    thread.start()
    return _TrayHandle(icon)


class _Icon(Protocol):
    def stop(self) -> None: ...


class _TrayHandle:
    def __init__(self, icon: _Icon) -> None:
        self._icon = icon

    def stop(self) -> None:
        self._icon.stop()


def register_hotkey(hotkey: str, callback: Callable[[], None]) -> Callable[[], None] | None:
    try:
        keyboard = importlib.import_module("keyboard")
    except ImportError:
        return None
    try:
        keyboard.add_hotkey(hotkey, callback)
    except Exception:
        return None

    def unregister() -> None:
        with _suppress():
            keyboard.remove_hotkey(hotkey)

    return unregister


class _suppress:
    def __enter__(self) -> None:
        return None

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> bool:
        return True


def show_window(window: object) -> None:
    _show(window)


def _show(window: object) -> None:
    show = getattr(window, "show", None)
    if callable(show):
        show()


def _hide(window: object) -> None:
    hide = getattr(window, "hide", None)
    if callable(hide):
        hide()


def _quit(window: object) -> None:
    destroy = getattr(window, "destroy", None)
    if callable(destroy):
        destroy()
