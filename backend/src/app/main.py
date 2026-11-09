from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path, PurePath

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.error_handlers import register_exception_handlers
from app.api.health import router as health_router
from app.api.tools import router as tools_router
from app.core.config import settings
from app.core.db import bootstrap_database
from app.core.logging import configure_logging
from app.core.paths import ensure_data_dirs, resolve_data_dir
from app.core.security import RequestBodyLimitMiddleware

_ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]


def initialize_app_data(data_dir: PurePath) -> Path:
    """创建数据目录并 bootstrap SQLite; 重复调用幂等。"""
    root = ensure_data_dirs(data_dir)
    bootstrap_database(root / "db" / "app.sqlite3").close()
    return root


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    data_dir = initialize_app_data(resolve_data_dir())
    configure_logging(data_dir)
    yield


def create_app() -> FastAPI:
    """应用工厂: 测试可以在此之上挂测试路由, 不污染生产实例。"""
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    # 先加内层, 后加外层: CORS 需要包住请求体限制, 413 响应也带白名单头
    app.add_middleware(RequestBodyLimitMiddleware, max_body_bytes=settings.max_request_body_bytes)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=_ALLOWED_METHODS,
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(tools_router)
    return app


app = create_app()
