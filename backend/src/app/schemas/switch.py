"""008 一键切换的请求 / 响应模型。

预览与应用都只返回路径、hash、大小与字段级变更; 文件原文、渲染字节与密钥明文
一律不进入 API。所有字段显式建模, 不使用裸 `dict` / `Any`。
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.adapters.base import WriteBlockerCode, WriteWarningCode
from app.core.format_edits import DocumentFormat
from app.core.paths import validate_absolute_path
from app.core.redaction import redact_text
from app.schemas.profile import BindingView, ModelEntry
from app.schemas.snapshot import FileObservation, SnapshotChange
from app.schemas.write import WrittenFileView

SwitchFileAction = Literal["created", "updated", "unchanged"]
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _normalize_non_blank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("字段不能为空")
    return normalized


def _validate_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("sha256 必须是 64 位小写十六进制")
    return value


class SwitchPreviewRequest(BaseModel):
    """预览请求; `model` 省略时使用档案清单第一项。"""

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str
    model: str | None = None

    @field_validator("tool_id", "profile_id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return _normalize_non_blank(value)

    @field_validator("model")
    @classmethod
    def _validate_model(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_non_blank(value)


class SwitchApplyRequest(SwitchPreviewRequest):
    """应用请求; 必须原样回传预览返回的 digest 与观察值。"""

    preview_digest: str
    observations: list[FileObservation] = Field(default_factory=list)

    @field_validator("preview_digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        validated = _validate_sha256(value)
        assert validated is not None
        return validated

    @model_validator(mode="after")
    def _check_unique_observations(self) -> SwitchApplyRequest:
        paths = [observation.path for observation in self.observations]
        if len(paths) != len(set(paths)):
            raise ValueError("observations 包含重复路径")
        return self


class SwitchBlocker(BaseModel):
    """阻止应用的原因; `path` 指向具体目标文件。"""

    model_config = ConfigDict(extra="forbid")

    code: WriteBlockerCode
    message: str
    path: str | None = None

    @field_validator("message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        return redact_text(value)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_absolute_path(value, label="blocker 路径")


class SwitchWarning(BaseModel):
    """不阻止应用、但必须让用户看到的提示。"""

    model_config = ConfigDict(extra="forbid")

    code: WriteWarningCode
    message: str

    @field_validator("message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        return redact_text(value)


class SwitchFilePreview(BaseModel):
    """单个目标文件的预览; 不含文件内容。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    format: DocumentFormat
    action: SwitchFileAction
    before_sha256: str | None = None
    after_sha256: str
    before_size: int = Field(ge=0)
    after_size: int = Field(ge=0)
    changes: list[SnapshotChange] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return validate_absolute_path(value, label="预览文件路径")

    @field_validator("before_sha256", "after_sha256")
    @classmethod
    def _validate_hash(cls, value: str | None) -> str | None:
        return _validate_sha256(value)


class SwitchPreviewResponse(BaseModel):
    """一次只读预览的完整结果; `preview_digest` 用于 apply 防漂移。"""

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str
    model: str | None = None
    available_models: list[ModelEntry] = Field(default_factory=list)
    files: list[SwitchFilePreview] = Field(default_factory=list)
    blockers: list[SwitchBlocker] = Field(default_factory=list)
    warnings: list[SwitchWarning] = Field(default_factory=list)
    restart_required: bool
    restart_message: str
    observations: list[FileObservation] = Field(default_factory=list)
    preview_digest: str
    can_apply: bool

    @field_validator("preview_digest")
    @classmethod
    def _validate_digest(cls, value: str) -> str:
        validated = _validate_sha256(value)
        assert validated is not None
        return validated

    @field_validator("restart_message")
    @classmethod
    def _redact_restart_message(cls, value: str) -> str:
        return redact_text(value)


class SwitchApplyResponse(BaseModel):
    """应用成功结果; 快照、审计与绑定都可追溯。"""

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str
    snapshot_id: str
    audit_id: str
    files: list[WrittenFileView] = Field(default_factory=list)
    binding: BindingView
    warnings: list[SwitchWarning] = Field(default_factory=list)
    restart_required: bool
    restart_message: str
    applied_at: datetime

    @field_validator("applied_at")
    @classmethod
    def _validate_applied_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("应用时间必须带时区")
        return value
