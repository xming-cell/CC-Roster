"""工具适配器协议与只读 / 写入契约模型。

契约见 `docs/decisions.md` 附录 A。`detect` / `read` 一律不得写盘, 也不做网络请求;
`plan` / `render` / `verify` 是 008 的纯函数写契约: `plan` 只读输入, `render` 只做
内存渲染, 两者都不触碰磁盘。真正的原子写、快照与审计由 007 的 `WriteEngine` 负责。
"""

from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.format_edits import DocumentFormat, FieldEdit
from app.core.paths import validate_absolute_path
from app.core.redaction import redact_text
from app.schemas.profile import Profile, ProfileProtocol
from app.schemas.snapshot import SnapshotChange

# 稳定契约: 新增类型必须先扩展这里, 不允许适配器自造 code。
WarningCode = Literal[
    "PARSE_ERROR",
    "PERMISSION_DENIED",
    "UNKNOWN_FORMAT",
    "UNSUPPORTED_VERSION",
    "CONFIG_EMPTY",
    "NO_MANAGED_FIELDS",
    "SECRET_IN_ENV",
    "ADAPTER_ERROR",
]

# 出现这些 warning 时条目状态为 error; 其余 warning 只做提示, 不改变状态。
ERROR_WARNING_CODES: frozenset[WarningCode] = frozenset(
    {"PARSE_ERROR", "PERMISSION_DENIED", "UNKNOWN_FORMAT", "UNSUPPORTED_VERSION"}
)


class ToolWarning(BaseModel):
    """可展示的降级原因: code 是稳定契约, message 是给人看的说明。"""

    code: WarningCode
    message: str

    @field_validator("message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        """warning 可能拼接外部文本; 统一在构造边界脱敏, 防止密钥进响应或日志。"""
        return redact_text(value)


class ToolCapabilities(BaseModel):
    """004 的能力基线; 后续卡按实际实现更新。"""

    read: bool = True
    write: bool = False
    sessions: bool = False
    launch: bool = False
    write_mode: Literal["none", "managed_fields"] = "none"


class ToolDetection(BaseModel):
    """`detect()` 的返回值: 只描述安装 / 配置状态, 不展开托管字段。"""

    installed: bool
    configured: bool
    version: str | None = None
    config_path: str | None = None
    last_modified: datetime | None = None
    warnings: list[ToolWarning] = Field(default_factory=list)


class ToolReadResult(BaseModel):
    """`read()` 的返回值: 已脱敏的托管字段与解析 warnings。"""

    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    is_third_party: bool | None = None
    has_secret: bool = False
    secret_preview: str | None = None
    warnings: list[ToolWarning] = Field(default_factory=list)


# 写契约的稳定 code 集合; 适配器只产生其中与文件映射相关的一部分, 其余由 service
# 在读取档案 / 密钥 / 权限时补齐。新增 code 必须先扩展这里。
WriteBlockerCode = Literal[
    "PROTOCOL_MISMATCH",
    "MODEL_UNKNOWN",
    "SECRET_MISSING",
    "SECRET_STORE_ERROR",
    "PARSE_ERROR",
    "UNSUPPORTED_VERSION",
    "UNSAFE_WRITE",
    "PERMISSION_DENIED",
    "FILE_NOT_WRITABLE",
    "DIRECTORY_NOT_WRITABLE",
    "ENV_KEY_CONFLICT",
]

WriteWarningCode = Literal[
    "PROFILE_SECRET_EMPTY",
    "NO_MODELS",
    "MODEL_SHADOWED",
    "OAUTH_AUTH_PRESENT",
]


class ToolBlocker(BaseModel):
    """阻止 apply 的原因; `path` 指向具体目标文件 (协议 / 档案级 blocker 为 None)。"""

    model_config = ConfigDict(extra="forbid")

    code: WriteBlockerCode
    message: str
    path: str | None = None

    @field_validator("message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        return redact_text(value)


class ToolPlanWarning(BaseModel):
    """不阻止 apply、但必须让用户看到的降级 / 回退提示。"""

    model_config = ConfigDict(extra="forbid")

    code: WriteWarningCode
    message: str

    @field_validator("message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        return redact_text(value)


class ToolCurrentFile(BaseModel):
    """适配器 `plan` 看到的目标文件现状; `data=None` 且 `exists=False` 表示缺失。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    exists: bool
    data: bytes | None = Field(default=None, strict=True)

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _require_absolute(value)

    @model_validator(mode="after")
    def _check_data_consistency(self) -> "ToolCurrentFile":
        if self.exists and self.data is None:
            raise ValueError("存在的文件必须提供字节")
        if not self.exists and self.data is not None:
            raise ValueError("不存在的文件不能提供字节")
        return self


class ToolPlanFile(BaseModel):
    """一个目标文件的纯内存编辑计划; 由 service 调用 `render` 得到最终字节。"""

    model_config = ConfigDict(extra="forbid")

    path: str
    format: DocumentFormat
    edits: list[FieldEdit] = Field(default_factory=list)
    changes: list[SnapshotChange] = Field(default_factory=list)
    create: bool = True

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        return _require_absolute(value)


class ToolPlan(BaseModel):
    """一次 `plan` 的完整结果: 文件计划、blockers、warnings 与重启要求。"""

    model_config = ConfigDict(extra="forbid")

    files: list[ToolPlanFile] = Field(default_factory=list)
    blockers: list[ToolBlocker] = Field(default_factory=list)
    warnings: list[ToolPlanWarning] = Field(default_factory=list)
    restart_required: bool = True
    restart_message: str


def _require_absolute(value: str) -> str:
    return validate_absolute_path(value, label="写入文件路径")


class ToolAdapter(Protocol):
    """显式注册的适配器契约。

    `managed_paths` 只声明本适配器会读取的文件, 供只读校验与展示使用;
    `detect` / `read` 必须容忍文件缺失、损坏与无权限, 返回 warnings 而不是抛异常。
    """

    @property
    def id(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    @property
    def capabilities(self) -> ToolCapabilities: ...

    @property
    def supported_protocols(self) -> tuple[ProfileProtocol, ...]: ...

    @property
    def managed_paths(self) -> tuple[Path, ...]: ...

    def detect(self) -> ToolDetection: ...

    def read(self) -> ToolReadResult: ...

    def plan(
        self,
        profile: Profile,
        *,
        secret: str | None,
        model: str | None,
        current: Mapping[str, ToolCurrentFile],
    ) -> ToolPlan: ...

    def render(self, plan_file: ToolPlanFile, original_bytes: bytes) -> bytes: ...

    def verify(
        self,
        plan_file: ToolPlanFile,
        original_bytes: bytes,
        rendered_bytes: bytes,
    ) -> None: ...
