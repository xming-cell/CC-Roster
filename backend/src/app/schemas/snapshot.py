"""快照领域模型与对外视图, 规则见 `specs/007-snapshot-kernel/spec.md`。

快照只保存内容块的 SHA-256 引用; 原始字节在 `snapshots/objects/` 内, 绝不进入
视图或 API 响应。变更展示值在构造时脱敏并截断, 仓储写 `meta.json` 前再脱敏一次。
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Final, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

from app.core.paths import validate_absolute_path
from app.core.redaction import redact_text

SNAPSHOT_SCHEMA_VERSION: Final[Literal[1]] = 1
SnapshotReason = Literal["apply", "rollback"]
SnapshotChangeAction = Literal["set", "remove"]
SnapshotWarningCode = Literal["SNAPSHOT_UNREADABLE", "SNAPSHOT_VERSION_UNSUPPORTED"]

MAX_CHANGE_VALUE_LENGTH = 200
_CHANGE_ELLIPSIS = "…"
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


def _require_uuid4(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("快照 id 必须是 UUID4") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise ValueError("快照 id 必须是规范小写的 UUID4")
    return value


def _require_sha256(value: str | None) -> str | None:
    if value is None:
        return None
    if _SHA256_PATTERN.fullmatch(value) is None:
        raise ValueError("sha256 必须是 64 位小写十六进制")
    return value


def _require_non_blank(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("字段不能为空")
    return normalized


def _require_absolute_path(value: str) -> str:
    return validate_absolute_path(value, label="快照文件路径")


def _redact_display(value: str | None) -> str | None:
    if value is None:
        return None
    redacted = redact_text(value)
    if len(redacted) <= MAX_CHANGE_VALUE_LENGTH:
        return redacted
    return redacted[:MAX_CHANGE_VALUE_LENGTH] + _CHANGE_ELLIPSIS


class SnapshotFile(BaseModel):
    """快照里的一个文件; `existed=false` 表示捕获时文件本来就不存在。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    path: str
    existed: bool
    sha256: str | None = None
    size: int = Field(ge=0)
    mtime_ns: int | None = Field(default=None, ge=0)
    mode: int | None = Field(default=None, ge=0, le=0o7777)
    chunks: list[str] = Field(default_factory=list)
    chunk_size: int = Field(gt=0)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _require_absolute_path(value)

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str | None) -> str | None:
        return _require_sha256(value)

    @field_validator("chunks")
    @classmethod
    def _validate_chunks(cls, value: list[str]) -> list[str]:
        for digest in value:
            if _SHA256_PATTERN.fullmatch(digest) is None:
                raise ValueError("chunk hash 必须是 64 位小写十六进制")
        return value

    @model_validator(mode="after")
    def _check_content_consistency(self) -> Self:
        if self.existed:
            if self.sha256 is None:
                raise ValueError("存在的文件必须有 sha256")
            if self.mtime_ns is None:
                raise ValueError("存在的文件必须有 mtime_ns")
            expected_chunks = (self.size + self.chunk_size - 1) // self.chunk_size
            if len(self.chunks) != expected_chunks:
                raise ValueError("chunk 数量与文件大小不一致")
        elif (
            self.sha256 is not None
            or self.size != 0
            or self.mtime_ns is not None
            or self.mode is not None
            or self.chunks
        ):
            raise ValueError("不存在的文件不能带内容、时间或权限")
        return self


class SnapshotFileSource(BaseModel):
    """写引擎交给快照仓储的同一份已校验字节; 不落盘、不再次读目标文件。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    existed: bool
    data: bytes | None = Field(default=None, strict=True)
    mtime_ns: int | None = Field(default=None, ge=0)
    mode: int | None = Field(default=None, ge=0, le=0o7777)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _require_absolute_path(value)

    @model_validator(mode="after")
    def _check_source_consistency(self) -> Self:
        if self.existed:
            if self.data is None:
                raise ValueError("存在的文件必须提供字节")
            if self.mtime_ns is None:
                raise ValueError("存在的文件必须提供 mtime_ns")
        elif self.data is not None or self.mtime_ns is not None or self.mode is not None:
            raise ValueError("不存在的文件不能提供字节、时间或权限")
        return self


class SnapshotChange(BaseModel):
    """一条展示用字段变更; before / after 在构造时就脱敏并截断。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    path: str
    field: str
    action: SnapshotChangeAction
    before: str | None = None
    after: str | None = None

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _require_absolute_path(value)

    @field_validator("field")
    @classmethod
    def _validate_field(cls, value: str) -> str:
        return _require_non_blank(value)

    @field_validator("before", "after")
    @classmethod
    def _redact_value(cls, value: str | None) -> str | None:
        return _redact_display(value)


class Snapshot(BaseModel):
    """持久化在 `<data>/snapshots/<id>/meta.json` 的完整快照元数据。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    schema_version: Literal[1] = SNAPSHOT_SCHEMA_VERSION
    id: str
    tool_id: str
    profile_id: str | None = None
    created_at: datetime
    reason: SnapshotReason
    pinned: bool = False
    files: list[SnapshotFile] = Field(default_factory=list)
    changes: list[SnapshotChange] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return _require_uuid4(value)

    @field_validator("tool_id")
    @classmethod
    def _validate_tool_id(cls, value: str) -> str:
        return _require_non_blank(value)

    @field_validator("profile_id")
    @classmethod
    def _validate_profile_id(cls, value: str | None) -> str | None:
        return None if value is None else _require_non_blank(value)

    @field_validator("created_at")
    @classmethod
    def _validate_created_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("创建时间必须带时区")
        return value

    @model_validator(mode="after")
    def _check_unique_paths(self) -> Self:
        paths = [file.path for file in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("快照文件路径重复")
        return self

    def to_view(self) -> SnapshotView:
        return SnapshotView(
            schema_version=self.schema_version,
            id=self.id,
            tool_id=self.tool_id,
            profile_id=self.profile_id,
            created_at=self.created_at,
            reason=self.reason,
            pinned=self.pinned,
            files=[_file_view(file) for file in self.files],
            changes=list(self.changes),
        )

    def to_summary(self) -> SnapshotSummary:
        return SnapshotSummary(
            id=self.id,
            tool_id=self.tool_id,
            profile_id=self.profile_id,
            created_at=self.created_at,
            reason=self.reason,
            pinned=self.pinned,
            file_count=len(self.files),
            total_size=sum(file.size for file in self.files),
            files=[_file_view(file) for file in self.files],
            changes=list(self.changes),
        )


class SnapshotFileView(BaseModel):
    """文件的对外视图: 只暴露 hash / 大小 / 时间, 不暴露 chunk 内容。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    existed: bool
    sha256: str | None
    size: int
    mtime_ns: int | None
    mode: int | None


class SnapshotView(BaseModel):
    """快照详情; 不含任何可直接还原的块内容。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    id: str
    tool_id: str
    profile_id: str | None
    created_at: datetime
    reason: SnapshotReason
    pinned: bool
    files: list[SnapshotFileView] = Field(default_factory=list)
    changes: list[SnapshotChange] = Field(default_factory=list)


class SnapshotSummary(BaseModel):
    """列表项: 文件与变更摘要, 同样不含块内容。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    tool_id: str
    profile_id: str | None
    created_at: datetime
    reason: SnapshotReason
    pinned: bool
    file_count: int
    total_size: int
    files: list[SnapshotFileView] = Field(default_factory=list)
    changes: list[SnapshotChange] = Field(default_factory=list)


class SnapshotWarning(BaseModel):
    """单份快照损坏时的列表级降级提示; 消息本身也脱敏。"""

    model_config = ConfigDict(extra="forbid")

    code: SnapshotWarningCode
    message: str

    @field_validator("message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        return redact_text(value)


class SnapshotListResponse(BaseModel):
    """快照列表响应; `retention_limit` 来自当前配置。"""

    model_config = ConfigDict(extra="forbid")

    snapshots: list[SnapshotSummary] = Field(default_factory=list)
    retention_limit: int = Field(ge=1, le=1000)
    warnings: list[SnapshotWarning] = Field(default_factory=list)


class SnapshotPinRequest(BaseModel):
    """`PATCH /api/snapshots/{id}` 的请求体。"""

    model_config = ConfigDict(extra="forbid")

    pinned: StrictBool


class RestoredFileView(BaseModel):
    """回滚结果里单个文件的动作与结果 hash。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    action: Literal["restored", "deleted", "unchanged"]
    sha256: str | None = None
    size: int = 0


class RollbackResponse(BaseModel):
    """回滚结果; 预回滚快照可用于再次恢复。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    pre_rollback_snapshot_id: str
    files: list[RestoredFileView] = Field(default_factory=list)


class FileObservation(BaseModel):
    """预览时记录、apply 时比对的只读文件观察值。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    exists: bool
    sha256: str | None = None
    size: int = Field(default=0, ge=0)
    mtime_ns: int | None = Field(default=None, ge=0)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _require_absolute_path(value)

    @field_validator("sha256")
    @classmethod
    def _validate_sha256(cls, value: str | None) -> str | None:
        return _require_sha256(value)

    @model_validator(mode="after")
    def _check_observation_consistency(self) -> Self:
        if self.exists:
            if self.sha256 is None or self.mtime_ns is None:
                raise ValueError("存在的文件必须有 sha256 与 mtime_ns")
        elif self.sha256 is not None or self.size != 0 or self.mtime_ns is not None:
            raise ValueError("不存在的文件不能带 hash、大小或时间")
        return self


def _file_view(file: SnapshotFile) -> SnapshotFileView:
    return SnapshotFileView(
        path=file.path,
        existed=file.existed,
        sha256=file.sha256,
        size=file.size,
        mtime_ns=file.mtime_ns,
        mode=file.mode,
    )
