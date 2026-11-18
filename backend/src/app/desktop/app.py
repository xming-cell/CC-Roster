"""桌面模式的应用工厂: 静态前端 + 同源写请求校验。"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from app.main import create_app

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class DesktopOriginMiddleware(BaseHTTPMiddleware):
    """拒绝其他网页对本地写接口的跨源调用; 无 Origin 的 CLI 请求放行。"""

    def __init__(self, app: Callable[..., Awaitable[None]], allowed_origins: set[str]) -> None:
        super().__init__(app)
        self._allowed = allowed_origins

    async def dispatch(
        self, request: Request, call_next: Callable[..., Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin")
        if (
            request.method in _WRITE_METHODS
            and request.url.path.startswith("/api/")
            and origin is not None
            and origin not in self._allowed
        ):
            return JSONResponse(
                status_code=403,
                content={"code": "ORIGIN_DENIED", "message": "拒绝来自非桌面窗口的写请求"},
            )
        return await call_next(request)


def create_desktop_app(frontend_dist: Path, *, port: int) -> FastAPI:
    app = create_app()
    allowed = {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}
    app.add_middleware(DesktopOriginMiddleware, allowed_origins=allowed)
    if frontend_dist.is_dir():
        app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="desktop-frontend")
    else:

        @app.get("/", response_class=HTMLResponse)
        def missing_frontend() -> str:
            return (
                "<!doctype html><meta charset='utf-8'>"
                "<title>CC-Roster</title>"
                "<h1>CC-Roster 桌面壳</h1>"
                "<p>前端尚未构建。请在 frontend 目录运行 <code>pnpm build</code> 后重启。</p>"
            )

    return app
