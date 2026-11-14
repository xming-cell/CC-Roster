"""统一错误模型。

业务代码只抛 `AppError`, 由 `app.api.error_handlers` 转成固定形状 `{code, message}`;
错误码是前端可判断的稳定契约, message 是给人看的说明。冲突与预览过期额外携带
可选 `details`, 其他错误仍只序列化 `{code, message}`。
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.core.redaction import redact_text
from app.schemas.snapshot import FileObservation


class AppError(Exception):
    """可预期的业务错误。未知异常不允许伪装成 AppError。"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        *,
        details: ErrorDetails | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


FileConflictReason = Literal["MISSING", "CREATED", "CONTENT_CHANGED"]


class FileConflict(BaseModel):
    """单个文件的外部改动详情; `expected` 是预览时的观察值。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    reason: FileConflictReason
    expected: FileObservation
    actual: FileObservation


class ErrorDetails(BaseModel):
    """409 的可读详情; 两种字段都只在该错误类型下出现。"""

    model_config = ConfigDict(extra="forbid")

    conflicts: list[FileConflict] | None = None
    stale_paths: list[str] | None = None


class ErrorResponse(BaseModel):
    code: str
    message: str
    details: ErrorDetails | None = None


class WriteConflict(AppError):
    """一个或多个目标文件在预览后发生变化, 整体拒绝写入。"""

    def __init__(self, conflicts: Sequence[FileConflict]) -> None:
        if not conflicts:
            raise ValueError("WriteConflict requires at least one conflict")
        self.conflicts = list(conflicts)
        first = self.conflicts[0]
        message = redact_text(
            f"{len(self.conflicts)} 个文件在预览后发生变化, 已拒绝写入: "
            f"{first.path} ({first.reason})"
        )
        super().__init__(
            "WRITE_CONFLICT",
            message,
            409,
            details=ErrorDetails(conflicts=self.conflicts),
        )
