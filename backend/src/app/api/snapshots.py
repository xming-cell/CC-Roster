"""快照列表 / 详情 / pin / 回滚 API。

端点只做参数绑定与转发; 业务在 `SnapshotService`, 数据访问在仓储。响应只含
路径、hash、大小、时间与变更摘要, 不提供任何快照内容下载。
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.config import settings
from app.core.paths import resolve_data_dir
from app.repositories.audit import AuditRepository
from app.repositories.snapshots import SnapshotRepository
from app.schemas.snapshot import (
    RollbackResponse,
    SnapshotListResponse,
    SnapshotPinRequest,
    SnapshotView,
)
from app.services.snapshot_service import SnapshotService

router = APIRouter(tags=["snapshots"])

DEFAULT_LIST_LIMIT = 50
MAX_LIST_LIMIT = 200


def get_snapshot_service() -> SnapshotService:
    """每个请求按当前数据目录与配置构造服务, 不做进程内缓存。"""
    data_dir = Path(resolve_data_dir())
    return SnapshotService(
        SnapshotRepository(
            data_dir,
            retention_limit=settings.snapshot_retention,
        ),
        AuditRepository(data_dir / "db" / "app.sqlite3"),
        write_lock_path=data_dir / "locks" / "write.lock",
    )


SnapshotServiceDep = Annotated[SnapshotService, Depends(get_snapshot_service)]


@router.get("/api/snapshots", response_model=SnapshotListResponse)
def list_snapshots(
    service: SnapshotServiceDep,
    tool_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIST_LIMIT)] = DEFAULT_LIST_LIMIT,
) -> SnapshotListResponse:
    return service.list_snapshots(tool_id=tool_id, limit=limit)


@router.get("/api/snapshots/{snapshot_id}", response_model=SnapshotView)
def get_snapshot(snapshot_id: str, service: SnapshotServiceDep) -> SnapshotView:
    return service.get_snapshot(snapshot_id)


@router.patch("/api/snapshots/{snapshot_id}", response_model=SnapshotView)
def set_snapshot_pinned(
    snapshot_id: str,
    payload: SnapshotPinRequest,
    service: SnapshotServiceDep,
) -> SnapshotView:
    return service.set_pinned(snapshot_id, payload.pinned)


@router.post("/api/snapshots/{snapshot_id}/rollback", response_model=RollbackResponse)
def rollback_snapshot(snapshot_id: str, service: SnapshotServiceDep) -> RollbackResponse:
    return service.rollback(snapshot_id)
