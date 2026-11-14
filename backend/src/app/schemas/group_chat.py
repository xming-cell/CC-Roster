"""群聊对比的请求 / 结果模型。"""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.paths import validate_absolute_path
from app.core.redaction import redact_text

MAX_PARTICIPANTS = 4
MAX_QUESTION_LENGTH = 8000


class GroupParticipant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str
    model: str | None = None

    @field_validator("tool_id", "profile_id")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("不能为空")
        return normalized

    @field_validator("model")
    @classmethod
    def _model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if any(not (character.isalnum() or character in "._:/-") for character in normalized):
            raise ValueError("模型标识包含不支持的字符")
        return normalized


class GroupChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    project_dir: str
    question: str
    participants: list[GroupParticipant]
    timeout_seconds: float = Field(default=120, ge=1, le=600)

    @field_validator("group_id")
    @classmethod
    def _group_id(cls, value: str) -> str:
        try:
            parsed = uuid.UUID(value)
        except ValueError as exc:
            raise ValueError("group_id 必须是 UUID") from exc
        return str(parsed)

    @field_validator("project_dir")
    @classmethod
    def _absolute(cls, value: str) -> str:
        return validate_absolute_path(value, label="项目目录")

    @field_validator("question")
    @classmethod
    def _question(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("问题不能为空")
        if len(normalized) > MAX_QUESTION_LENGTH:
            raise ValueError(f"问题最长 {MAX_QUESTION_LENGTH} 个字符")
        return normalized

    @model_validator(mode="after")
    def _participants(self) -> "GroupChatRequest":
        if not 1 <= len(self.participants) <= MAX_PARTICIPANTS:
            raise ValueError(f"参与者数量必须在 1-{MAX_PARTICIPANTS} 之间")
        keys = [(item.tool_id, item.profile_id, item.model) for item in self.participants]
        if len(keys) != len(set(keys)):
            raise ValueError("参与者不能重复")
        return self


GroupResultStatus = Literal["success", "failed", "timeout"]


class GroupChatResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str
    model: str | None = None
    status: GroupResultStatus
    content: str = ""
    error: str | None = None
    duration_ms: int = Field(ge=0)

    @field_validator("content", "error")
    @classmethod
    def _redact(cls, value: str | None) -> str | None:
        return None if value is None else redact_text(value)


class GroupChatResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    group_id: str
    question: str
    results: list[GroupChatResult] = Field(default_factory=list)
    completed_at: datetime

    @field_validator("completed_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("时间必须带时区")
        return value


class GroupCancelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cancelled: bool
    message: str
