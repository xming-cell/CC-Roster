"""工具适配器协议与只读结果模型。

契约见 `docs/decisions.md` 附录 A。004 只落地只读子集:
`detect` / `read` 一律不得写盘, 也不做网络请求; 写、会话、启动能力由后续卡扩展。
"""

from datetime import datetime
from pathlib import Path
from typing import Literal, Protocol

from pydantic import BaseModel, Field, field_validator

from app.core.redaction import redact_text

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
    def managed_paths(self) -> tuple[Path, ...]: ...

    def detect(self) -> ToolDetection: ...

    def read(self) -> ToolReadResult: ...
