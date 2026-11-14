"""审计列表 API: 只返回可展示摘要, 读取失败由仓储转成 `AUDIT_UNREADABLE`。"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.paths import resolve_data_dir
from app.repositories.audit import DEFAULT_AUDIT_LIMIT, AuditRepository
from app.schemas.audit import AuditListResponse
from app.services.audit_service import AuditService

router = APIRouter(tags=["audit"])

MAX_AUDIT_LIMIT = 200


def get_audit_service() -> AuditService:
    """每个请求按当前数据目录构造服务, 不在进程内缓存连接。"""
    data_dir = Path(resolve_data_dir())
    return AuditService(AuditRepository(data_dir / "db" / "app.sqlite3"))


AuditServiceDep = Annotated[AuditService, Depends(get_audit_service)]


@router.get("/api/audit", response_model=AuditListResponse)
def list_audit_entries(
    service: AuditServiceDep,
    tool_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_AUDIT_LIMIT)] = DEFAULT_AUDIT_LIMIT,
) -> AuditListResponse:
    return service.list_entries(tool_id=tool_id, limit=limit)
