"""供应商档案的领域模型与 `profiles.json` 根结构。

档案只保存 `SecretRef`, 不保存明文密钥; 时间字段必须带时区。
`ProfileStore` 是持久化文件的内存形态, 仓储在读取和写入前都经过它校验。
"""

import uuid
from datetime import datetime
from typing import Final, Literal, Self
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.redaction import redact_text

PROFILE_STORE_SCHEMA_VERSION: Final[Literal[1]] = 1

ProfileProtocol = Literal["anthropic", "openai"]
SecretBackend = Literal["keyring", "file"]
SecretStoreBackend = Literal["keyring", "file", "unavailable"]
ProfileWarningCode = Literal["SECRET_MISSING", "SECRET_STORE_ERROR"]

MAX_MODEL_ID_LENGTH = 120
MAX_PROFILE_NAME_LENGTH = 80
MAX_BASE_URL_LENGTH = 2048
_ALLOWED_BASE_URL_SCHEMES = frozenset({"http", "https"})


def _normalize_profile_name(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("档案名称不能为空")
    if len(normalized) > MAX_PROFILE_NAME_LENGTH:
        raise ValueError(f"档案名称最长 {MAX_PROFILE_NAME_LENGTH} 个字符")
    return normalized


def _normalize_base_url(value: str) -> str:
    """只校验并去首尾空白, 不改写路径 / 端口 / 大小写。"""
    normalized = value.strip()
    if not normalized:
        raise ValueError("base_url 不能为空")
    if len(normalized) > MAX_BASE_URL_LENGTH:
        raise ValueError(f"base_url 最长 {MAX_BASE_URL_LENGTH} 个字符")
    if any(character.isspace() for character in normalized):
        raise ValueError("base_url 不能包含空白字符")
    try:
        parts = urlsplit(normalized)
        _ = parts.port  # 访问 port 以触发非法端口校验
    except ValueError as exc:
        raise ValueError("base_url 不是合法的绝对地址") from exc
    if parts.scheme.lower() not in _ALLOWED_BASE_URL_SCHEMES:
        raise ValueError("base_url 必须是 http 或 https 绝对地址")
    if parts.hostname is None:
        raise ValueError("base_url 必须包含主机名")
    if parts.username is not None or parts.password is not None:
        raise ValueError("base_url 不能包含用户名或密码")
    if parts.fragment:
        raise ValueError("base_url 不能包含片段")
    return normalized


def _require_aware(value: datetime) -> datetime:
    """拒绝裸 `datetime.now()`, 与 `app.core.clock` 的约定保持一致。"""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("时间必须带时区")
    return value


def _require_uuid4(value: str) -> str:
    try:
        parsed = uuid.UUID(value)
    except ValueError as exc:
        raise ValueError("档案 id 必须是 UUID4") from exc
    if parsed.version != 4:
        raise ValueError("档案 id 必须是 UUID4")
    return str(parsed)


class ModelEntry(BaseModel):
    """档案里的一条模型清单; `id` 是模型标识, 不是数据库主键。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str
    display_name: str | None = None

    @field_validator("id")
    @classmethod
    def _normalize_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("模型标识不能为空")
        if len(normalized) > MAX_MODEL_ID_LENGTH:
            raise ValueError(f"模型标识最长 {MAX_MODEL_ID_LENGTH} 个字符")
        return normalized

    @field_validator("display_name")
    @classmethod
    def _normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class SecretRef(BaseModel):
    """密钥引用; 按 ADR-006 只记录位置, 不记录密钥本身。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str
    backend: SecretBackend
    locator: str

    @field_validator("id", "locator")
    @classmethod
    def _require_non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("密钥引用字段不能为空")
        return normalized


class SecretStoreStatus(BaseModel):
    """当前可用的密钥后端; `fallback=true` 时前端必须显示横幅。"""

    model_config = ConfigDict(extra="forbid")

    backend: SecretStoreBackend
    fallback: bool = False
    message: str | None = None


class Profile(BaseModel):
    """供应商档案; 同一份档案可以被多个工具绑定。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: str
    name: str
    protocol: ProfileProtocol
    base_url: str
    secret_ref: SecretRef | None = None
    models: list[ModelEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        return _require_uuid4(value)

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return _normalize_profile_name(value)

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        return _normalize_base_url(value)

    @field_validator("created_at", "updated_at")
    @classmethod
    def _validate_timestamps(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @model_validator(mode="after")
    def _check_secret_locator(self) -> Self:
        if self.secret_ref is not None and self.secret_ref.locator != self.id:
            raise ValueError("secret_ref.locator 必须等于档案 id")
        return self


class ToolBinding(BaseModel):
    """工具到档案的绑定; 006 只记录选择, `active` 恒为 false。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    tool_id: str
    profile_id: str
    bound_at: datetime
    active: bool = False
    applied_at: datetime | None = None
    snapshot_id: str | None = None

    @field_validator("tool_id", "profile_id")
    @classmethod
    def _require_non_blank(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("绑定字段不能为空")
        return normalized

    @field_validator("bound_at")
    @classmethod
    def _validate_bound_at(cls, value: datetime) -> datetime:
        return _require_aware(value)

    @field_validator("applied_at")
    @classmethod
    def _validate_applied_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return _require_aware(value)


class ProfileStore(BaseModel):
    """`profiles.json` 的根结构; 关系完整性在读取与写回时都校验。"""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = PROFILE_STORE_SCHEMA_VERSION
    profiles: list[Profile] = Field(default_factory=list)
    bindings: list[ToolBinding] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_integrity(self) -> Self:
        profile_ids = [profile.id for profile in self.profiles]
        if len(profile_ids) != len(set(profile_ids)):
            raise ValueError("档案 id 重复")

        tool_ids = [binding.tool_id for binding in self.bindings]
        if len(tool_ids) != len(set(tool_ids)):
            raise ValueError("同一工具出现多条绑定")

        known_profiles = set(profile_ids)
        if any(binding.profile_id not in known_profiles for binding in self.bindings):
            raise ValueError("绑定引用了不存在的档案")
        return self


class ProfileWarning(BaseModel):
    """档案级降级提示; 密钥缺失 / 存储失败不能伪装成「未设置密钥」。"""

    model_config = ConfigDict(extra="forbid")

    code: ProfileWarningCode
    message: str

    @field_validator("message")
    @classmethod
    def _redact_message(cls, value: str) -> str:
        return redact_text(value)


class ToolRef(BaseModel):
    """占用工具的结构化引用; 已卸载工具仍然参与删除保护。"""

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    display_name: str
    installed: bool


class ProfileView(BaseModel):
    """档案的对外视图: 只暴露密钥状态与脱敏预览, 不暴露 `SecretRef` / locator。"""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    protocol: ProfileProtocol
    base_url: str
    models: list[ModelEntry] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    has_secret: bool = False
    secret_preview: str | None = None
    secret_backend: SecretBackend | None = None
    used_by: list[ToolRef] = Field(default_factory=list)
    warnings: list[ProfileWarning] = Field(default_factory=list)


class BindingView(ToolBinding):
    """绑定的对外视图; 字段与持久化模型一致, 后续卡可独立扩展。"""


class BindProfileRequest(BaseModel):
    """把一个工具指向一份档案; 只写绑定关系, 不改工具配置文件。"""

    model_config = ConfigDict(extra="forbid")

    profile_id: str

    @field_validator("profile_id")
    @classmethod
    def _normalize_profile_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("profile_id 不能为空")
        return normalized


class BindingDeleteResponse(BaseModel):
    """解绑结果; `removed=false` 表示原本就没有绑定, 仍算成功。"""

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    removed: bool


class ProfileListResponse(BaseModel):
    """档案列表: 档案、绑定、密钥后端状态与列表级降级原因。"""

    model_config = ConfigDict(extra="forbid")

    profiles: list[ProfileView] = Field(default_factory=list)
    bindings: list[BindingView] = Field(default_factory=list)
    secret_store: SecretStoreStatus
    warnings: list[ProfileWarning] = Field(default_factory=list)


class ProfileCreate(BaseModel):
    """创建档案; `secret` 可省略表示暂不设置密钥。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    protocol: ProfileProtocol
    base_url: str
    models: list[ModelEntry] = Field(default_factory=list)
    secret: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        return _normalize_profile_name(value)

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, value: str) -> str:
        return _normalize_base_url(value)


class ProfileUpdate(BaseModel):
    """部分更新; 省略 `secret` 保持原密钥, 显式 `null` 表示清除。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    protocol: ProfileProtocol | None = None
    base_url: str | None = None
    models: list[ModelEntry] | None = None
    secret: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_profile_name(value)

    @field_validator("base_url")
    @classmethod
    def _check_base_url(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_base_url(value)


class ProfileCopyRequest(BaseModel):
    """复制档案; 省略名称时由服务生成「原名 (副本)」。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str | None) -> str | None:
        return None if value is None else _normalize_profile_name(value)


class ProfileDeleteResponse(BaseModel):
    """删除结果; `unbound_tools` 是随档案一起解除绑定的工具。"""

    model_config = ConfigDict(extra="forbid")

    deleted: bool
    unbound_tools: list[ToolRef] = Field(default_factory=list)
