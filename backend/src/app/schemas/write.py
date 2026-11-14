"""写引擎的输入 / 输出模型, 规则见 `specs/007-snapshot-kernel/spec.md`。

`WritePlan` 由 008 的 adapter 在预览阶段构造; 路径、观察值与待写字节必须来自同一次
读取。007 只消费计划, 不负责格式化 / 渲染。
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.paths import resolve_absolute_path
from app.schemas.snapshot import FileObservation, SnapshotChange

WriteFileAction = Literal["created", "updated", "unchanged"]


class PlannedFile(BaseModel):
    """一个待写文件: 前端观察值、最终字节与展示用变更。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    expected_bytes: bytes = Field(strict=True)
    observation: FileObservation
    changes: list[SnapshotChange] = Field(default_factory=list)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        try:
            resolved = resolve_absolute_path(Path(value), label="写入文件路径")
        except ValueError as exc:
            raise ValueError("写入文件路径必须是绝对路径且不能包含 .. 段") from exc
        if str(resolved) != value:
            raise ValueError("写入文件路径必须是已解析 symlink 的规范路径")
        return value

    @model_validator(mode="after")
    def _check_observation_matches_path(self) -> Self:
        if self.observation.path != self.path:
            raise ValueError("观察值路径必须与写入路径一致")
        return self


class WritePlan(BaseModel):
    """一次 apply 的完整计划; 所有路径必须唯一。"""

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str | None = None
    files: list[PlannedFile] = Field(default_factory=list)

    @field_validator("tool_id")
    @classmethod
    def _validate_tool_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("tool_id 不能为空")
        return normalized

    @field_validator("profile_id")
    @classmethod
    def _validate_profile_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("profile_id 不能为空")
        return normalized

    @model_validator(mode="after")
    def _check_unique_paths(self) -> Self:
        paths = [file.path for file in self.files]
        if len(paths) != len(set(paths)):
            raise ValueError("写入计划包含重复路径")
        return self


class WrittenFileView(BaseModel):
    """apply 成功后单个文件的结果; 不含文件内容。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    action: WriteFileAction
    sha256: str
    size: int = Field(ge=0)


class WriteResult(BaseModel):
    """apply 成功结果: 预写入快照与审计记录均可追溯。"""

    model_config = ConfigDict(extra="forbid")

    snapshot_id: str
    audit_id: str
    files: list[WrittenFileView] = Field(default_factory=list)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
