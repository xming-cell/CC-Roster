"""`python -m app.desktop`: 打开薄壳窗口, 退出时停后端。"""

from __future__ import annotations

import importlib
import sys
from typing import Protocol, cast

from app.core.paths import ensure_data_dirs, resolve_data_dir
from app.desktop.app import create_desktop_app
from app.desktop.server import DesktopServer, frontend_dist
from app.desktop.single_instance import DesktopAlreadyRunning, SingleInstance
from app.desktop.tray import build_tray, register_hotkey, show_window
from app.repositories.settings import SettingsRepository


class _WebviewModule(Protocol):
    def create_window(self, title: str, url: str, *, width: int, height: int) -> object: ...

    def start(self) -> None: ...


def main() -> int:
    data_dir = ensure_data_dirs(resolve_data_dir())
    instance = SingleInstance(data_dir)
    try:
        instance.acquire()
    except DesktopAlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        return 2
    server = DesktopServer(lambda port: create_desktop_app(frontend_dist(), port=port))
    try:
        url = server.start()
        try:
            webview = cast(_WebviewModule, importlib.import_module("webview"))
        except ImportError:
            print("桌面窗口需要可选依赖 pywebview。", file=sys.stderr)
            print("请运行: cd backend && uv sync --group desktop", file=sys.stderr)
            return 3
        window = webview.create_window("CC-Roster", url, width=1280, height=820)
        settings = SettingsRepository(data_dir).load()
        tray = build_tray(window)
        unregister = register_hotkey(settings.hotkey, lambda: show_window(window))
        if unregister is None:
            print("全局快捷键不可用, 已降级为仅托盘 / 窗口。", file=sys.stderr)
        try:
            webview.start()
        finally:
            if unregister is not None:
                unregister()
            if tray is not None:
                tray.stop()
        return 0
    finally:
        server.stop()
        instance.release()


if __name__ == "__main__":
    raise SystemExit(main())
