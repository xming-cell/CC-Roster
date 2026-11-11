"""审计查询用例: 只读最近记录, 数据访问全部留在仓储层。"""

from app.repositories.audit import DEFAULT_AUDIT_LIMIT, AuditRepository
from app.schemas.audit import AuditListResponse


class AuditService:
    """审计列表的用例边界; 仓储通过构造参数注入。"""

    def __init__(self, audit: AuditRepository) -> None:
        self._audit = audit

    def list_entries(
        self,
        *,
        tool_id: str | None = None,
        limit: int = DEFAULT_AUDIT_LIMIT,
    ) -> AuditListResponse:
        return AuditListResponse(entries=self._audit.list_recent(limit=limit, tool_id=tool_id))
