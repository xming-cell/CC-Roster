"""启动器请求 / 预览 / 结果模型。预览绝不包含密钥值。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.paths import validate_absolute_path
from app.core.redaction import redact_text

LaunchBlockerCode = Literal[
    "TOOL_NOT_INSTALLED",
    "PROTOCOL_MISMATCH",
    "SECRET_MISSING",
    "SECRET_STORE_ERROR",
    "PROJECT_DIR_NOT_FOUND",
    "PROJECT_DIR_NOT_DIRECTORY",
    "PROJECT_DIR_NOT_READABLE",
    "MODEL_MISSING",
    "PLATFORM_UNSUPPORTED",
    "LAUNCH_FAILED",
]


class LaunchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str
    project_dir: str
    model: str | None = None

    @field_validator("tool_id", "profile_id")
    @classmethod
    def _non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("不能为空")
        return normalized

    @field_validator("project_dir")
    @classmethod
    def _absolute_dir(cls, value: str) -> str:
        return validate_absolute_path(value, label="项目目录")

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


class LaunchBlocker(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: LaunchBlockerCode
    message: str

    @field_validator("message")
    @classmethod
    def _redact(cls, value: str) -> str:
        return redact_text(value)


class LaunchPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str
    model: str | None = None
    project_dir: str
    executable: str | None = None
    command: list[str] = Field(default_factory=list)
    environment_keys: list[str] = Field(default_factory=list)
    blockers: list[LaunchBlocker] = Field(default_factory=list)
    can_launch: bool = False


class LaunchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    profile_id: str
    project_dir: str
    launched: bool
    pid: int | None = None
    message: str

    @field_validator("message")
    @classmethod
    def _redact(cls, value: str) -> str:
        return redact_text(value)
