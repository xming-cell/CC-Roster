"""后端进程生命周期: 随机端口启动 uvicorn, 健康等待, 退出清理。"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Callable
from pathlib import Path

import uvicorn
from fastapi import FastAPI

DEFAULT_START_TIMEOUT_SECONDS = 15.0
LOOPBACK = "127.0.0.1"


class DesktopServerError(RuntimeError):
    """后端没有在限定时间内就绪。"""


class DesktopServer:
    def __init__(
        self,
        app_factory: Callable[[int], FastAPI],
        *,
        host: str = LOOPBACK,
        start_timeout: float = DEFAULT_START_TIMEOUT_SECONDS,
    ) -> None:
        if host != LOOPBACK:
            raise ValueError("桌面壳只允许监听 127.0.0.1")
        self._app_factory = app_factory
        self._host = host
        self._start_timeout = start_timeout
        self._server: uvicorn.Server | None = None
        self._thread: threading.Thread | None = None
        self._port: int | None = None

    @property
    def url(self) -> str:
        if self._port is None:
            raise DesktopServerError("server is not running")
        return f"http://{self._host}:{self._port}/"

    @property
    def port(self) -> int | None:
        return self._port

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> str:
        if self.running:
            raise DesktopServerError("server is already running")
        port = _reserve_port(self._host)
        config = uvicorn.Config(
            self._app_factory(port),
            host=self._host,
            port=port,
            log_level="warning",
            access_log=False,
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, name="cc-roster-desktop", daemon=True)
        self._server = server
        self._thread = thread
        self._port = port
        thread.start()
        deadline = time.monotonic() + self._start_timeout
        while time.monotonic() < deadline:
            if server.started:
                return self.url
            if not thread.is_alive():
                self._reset()
                raise DesktopServerError("后端线程提前退出")
            time.sleep(0.02)
        self.stop()
        raise DesktopServerError("后端启动超时")

    def stop(self) -> None:
        server = self._server
        thread = self._thread
        if server is not None:
            server.should_exit = True
        if thread is not None:
            thread.join(timeout=5.0)
        self._reset()

    def _reset(self) -> None:
        self._server = None
        self._thread = None
        self._port = None

    def __enter__(self) -> DesktopServer:
        self.start()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop()


def _reserve_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def frontend_dist() -> Path:
    """仓库内 `frontend/dist`; 不存在时桌面壳显示构建提示。"""
    return Path(__file__).resolve().parents[4] / "frontend" / "dist"
