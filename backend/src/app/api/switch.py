"""一键切换预览 / 应用 API。

端点只做参数绑定与转发; 预览无状态, 应用的写锁、快照、原子写与审计全部在
`SwitchService` 与 007 的 `WriteEngine` 内完成。
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from app.adapters.registry import build_registry
from app.core.config import settings
from app.core.paths import resolve_data_dir
from app.repositories.audit import AuditRepository
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import build_secret_store
from app.repositories.snapshots import SnapshotRepository
from app.schemas.switch import (
    SwitchApplyRequest,
    SwitchApplyResponse,
    SwitchPreviewRequest,
    SwitchPreviewResponse,
)
from app.services.snapshot_service import SnapshotService
from app.services.switch_service import SwitchService
from app.services.write_engine import WriteEngine

router = APIRouter(tags=["switch"])


def get_switch_service() -> SwitchService:
    """每个请求按当前数据目录与环境构造服务, 不做进程内缓存。"""
    data_dir = Path(resolve_data_dir())
    audit = AuditRepository(data_dir / "db" / "app.sqlite3")
    snapshots_repository = SnapshotRepository(
        data_dir,
        retention_limit=settings.snapshot_retention,
    )
    lock_path = data_dir / "locks" / "write.lock"
    return SwitchService(
        registry=build_registry(),
        profiles=ProfileRepository(data_dir),
        secrets=build_secret_store(data_dir, mode=settings.secret_backend),
        write_engine=WriteEngine(
            snapshots_repository,
            audit,
            write_lock_path=lock_path,
        ),
        snapshots=SnapshotService(
            snapshots_repository,
            audit,
            write_lock_path=lock_path,
        ),
        audit=audit,
    )


SwitchServiceDep = Annotated[SwitchService, Depends(get_switch_service)]


@router.post("/api/switch/preview", response_model=SwitchPreviewResponse)
def preview_switch(
    payload: SwitchPreviewRequest,
    service: SwitchServiceDep,
) -> SwitchPreviewResponse:
    return service.preview(payload)


@router.post("/api/switch/apply", response_model=SwitchApplyResponse)
def apply_switch(
    payload: SwitchApplyRequest,
    service: SwitchServiceDep,
) -> SwitchApplyResponse:
    return service.apply(payload)
