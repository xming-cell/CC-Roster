"""会话回放的稳定 schema。

会话是外部工具的原始记录, 本应用只读。消息内容在构造边界统一脱敏,
避免真实会话里贴过 key 时经由 API / 前端 / 日志泄露。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.adapters.base import ToolWarning
from app.core.redaction import redact_text

SessionRole = Literal["user", "assistant", "tool_call", "tool_result", "system", "unknown"]


def _require_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("时间必须带时区")
    return value


class SessionMessage(BaseModel):
    """统一消息模型; `raw_type` 保留外部事件类型便于排障。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    role: SessionRole
    timestamp: datetime | None = None
    content: str
    tool_name: str | None = None
    is_error: bool = False
    raw_type: str | None = None

    @field_validator("timestamp")
    @classmethod
    def _validate_timestamp(cls, value: datetime | None) -> datetime | None:
        return _require_aware(value)

    @field_validator("content")
    @classmethod
    def _redact_content(cls, value: str) -> str:
        return redact_text(value)


class SessionSummary(BaseModel):
    """列表项只含渲染所需信息, 不返回完整记录。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    tool_id: str
    title: str
    project_path: str | None = None
    started_at: datetime
    updated_at: datetime
    message_count: int | None = Field(default=None, ge=0)
    warnings: list[ToolWarning] = Field(default_factory=list)

    @field_validator("started_at", "updated_at")
    @classmethod
    def _validate_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("会话时间必须带时区")
        return value


class SessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: list[SessionSummary] = Field(default_factory=list)
    warnings: list[ToolWarning] = Field(default_factory=list)
    next_cursor: int | None = None
    has_more: bool = False


class SessionMessagesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    session_id: str
    messages: list[SessionMessage] = Field(default_factory=list)
    next_cursor: int | None = None
    has_more: bool = False
    total_messages: int | None = None
    warnings: list[ToolWarning] = Field(default_factory=list)
