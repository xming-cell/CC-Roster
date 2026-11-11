"""审计领域模型; 审计只存可展示摘要, 不存任何文件原文或密钥。"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AuditAction = Literal["apply", "rollback"]
AuditResult = Literal["success", "failed", "conflict"]


class AuditEntry(BaseModel):
    """`audit_entries` 表的一行。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    created_at: datetime
    action: AuditAction
    tool_id: str
    profile_id: str | None = None
    snapshot_id: str | None = None
    files: list[str] = Field(default_factory=list)
    fields: list[str] = Field(default_factory=list)
    result: AuditResult
    message: str

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("审计时间必须带时区")
        return value
