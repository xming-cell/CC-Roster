"""应用内对话的领域模型。

对话上下文只记录用户显式选择的工具 / 档案 / 目录; 消息内容在持久化与响应边界
统一脱敏。SSE 事件是前端可依赖的稳定契约。
"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.paths import validate_absolute_path
from app.core.redaction import redact_text

ChatStatus = Literal["idle", "running", "cancelled", "failed"]
ChatRole = Literal["user", "assistant", "tool", "system"]
ChatEventType = Literal["status", "token", "tool", "done", "error", "cancelled"]

MAX_MESSAGE_LENGTH = 8000
MAX_TITLE_LENGTH = 80


def _require_aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("时间必须带时区")
    return value


def _require_uuid4(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("会话 id 必须是 UUID4") from exc
    if parsed.version != 4:
        raise ValueError("会话 id 必须是 UUID4")
    return str(parsed)


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    role: ChatRole
    content: str
    created_at: datetime
    tool_name: str | None = None
    is_error: bool = False

    @field_validator("content")
    @classmethod
    def _redact(cls, value: str) -> str:
        return redact_text(value) if value else ""

    @field_validator("created_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_aware(value)


class ChatSession(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool_id: str
    profile_id: str
    project_dir: str
    title: str
    status: ChatStatus = "idle"
    messages: list[ChatMessage] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("id")
    @classmethod
    def _uuid(cls, value: str) -> str:
        return _require_uuid4(value)

    @field_validator("project_dir")
    @classmethod
    def _absolute(cls, value: str) -> str:
        return validate_absolute_path(value, label="项目目录")

    @field_validator("created_at", "updated_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        return _require_aware(value)


class ChatStore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    sessions: list[ChatSession] = Field(default_factory=list)


class ChatCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str
    project_dir: str
    title: str | None = None

    @field_validator("tool_id", "profile_id")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("不能为空")
        return normalized

    @field_validator("project_dir")
    @classmethod
    def _absolute(cls, value: str) -> str:
        return validate_absolute_path(value, label="项目目录")

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) > MAX_TITLE_LENGTH:
            raise ValueError(f"标题最长 {MAX_TITLE_LENGTH} 个字符")
        return normalized or None


class ChatSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str

    @field_validator("content")
    @classmethod
    def _content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("消息不能为空")
        if len(normalized) > MAX_MESSAGE_LENGTH:
            raise ValueError(f"消息最长 {MAX_MESSAGE_LENGTH} 个字符")
        return normalized


class ChatSessionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    tool_id: str
    profile_id: str
    project_dir: str
    title: str
    status: ChatStatus
    messages: list[ChatMessage]
    created_at: datetime
    updated_at: datetime


class ChatSessionListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sessions: list[ChatSessionView] = Field(default_factory=list)


class ChatEvent(BaseModel):
    """SSE data 的固定形状; 未使用字段保持 None。"""

    model_config = ConfigDict(extra="forbid")

    type: ChatEventType
    content: str | None = None
    status: str | None = None
    tool_name: str | None = None
    message: str | None = None


class ChatCancelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cancelled: bool
    message: str
