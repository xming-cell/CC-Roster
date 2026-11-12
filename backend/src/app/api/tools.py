"""只读工具发现 API。

端点用同步 `def`, 由 FastAPI 线程池承载文件读取, 避免阻塞事件循环;
服务按请求构造, 不在进程内缓存配置内容。未知工具统一由 `AppError` 转成 404。
"""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query

from app.adapters.registry import build_registry
from app.schemas.tool import ToolListResponse, ToolView
from app.services.tool_discovery import ToolDiscoveryService

ToolStatusFilter = Literal["ok", "unconfigured", "error"]

router = APIRouter(tags=["tools"])


def get_tool_service() -> ToolDiscoveryService:
    """每个请求读取一次当前环境 (PATH / home / 配置目录变量)。"""
    return ToolDiscoveryService(build_registry())


ToolService = Annotated[ToolDiscoveryService, Depends(get_tool_service)]


@router.get("/api/tools", response_model=ToolListResponse)
def list_tools(
    service: ToolService,
    name: Annotated[str | None, Query()] = None,
    provider: Annotated[str | None, Query()] = None,
    model: Annotated[str | None, Query()] = None,
    status: Annotated[ToolStatusFilter | None, Query()] = None,
) -> ToolListResponse:
    return service.list_tools(
        name=name,
        provider=provider,
        model=model,
        status=status,
    )


@router.get("/api/tools/{tool_id}", response_model=ToolView)
def get_tool(tool_id: str, service: ToolService) -> ToolView:
    return service.get_tool(tool_id)
