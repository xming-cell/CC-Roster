"""本地导入供应商的请求 / 响应模型。

文件格式(JSON / TOML, `schema_version: 1`):
{
  "schema_version": 1,
  "profiles": [
    {"name": "...", "protocol": "anthropic", "base_url": "https://...",
     "models": [{"id": "...", "display_name": null}], "secret": "sk-..."}
  ]
}
`profiles` 里的每一项按 `ProfileCreate` 校验; `secret` 可省略。
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SUPPORTED_IMPORT_VERSION = 1
MAX_IMPORT_CONTENT_BYTES = 1_000_000
MAX_IMPORT_ITEMS = 500

ImportItemStatus = Literal["new", "duplicate", "invalid"]
ImportPolicy = Literal["skip", "overwrite"]
ImportSource = Literal["content", "codex_config"]
ImportFormat = Literal["json", "toml"]


class ProfileImportRequest(BaseModel):
    """前端读取文件文本后提交; 不在服务端接收任意文件路径。"""

    model_config = ConfigDict(extra="forbid")

    content: str
    policy: ImportPolicy = "skip"

    @field_validator("content")
    @classmethod
    def _check_size(cls, value: str) -> str:
        if len(value.encode("utf-8")) > MAX_IMPORT_CONTENT_BYTES:
            raise ValueError(f"导入文件超过 {MAX_IMPORT_CONTENT_BYTES} 字节")
        return value


class ProfileImportTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    new: int = Field(ge=0)
    duplicate: int = Field(ge=0)
    invalid: int = Field(ge=0)


class ProfileImportItem(BaseModel):
    """预览里的一条判定; 不包含密钥。"""

    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    name: str | None = None
    status: ImportItemStatus
    reasons: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    has_secret: bool = False
    conflict_profile_id: str | None = None


class ProfileImportPreview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int
    items: list[ProfileImportItem] = Field(default_factory=list)
    totals: ProfileImportTotals
    can_import: bool
    source: ImportSource = "content"
    source_path: str | None = None
    format: ImportFormat = "json"


class ProfileImportResult(BaseModel):
    """导入结果; 不返回密钥或文件原文。"""

    model_config = ConfigDict(extra="forbid")

    imported: int = Field(ge=0)
    overwritten: int = Field(ge=0)
    skipped: int = Field(ge=0)
    profile_ids: list[str] = Field(default_factory=list)


class CodexProfileImportRequest(BaseModel):
    """直接读取 Codex 配置时只允许选择重复项策略。"""

    model_config = ConfigDict(extra="forbid")

    policy: ImportPolicy = "skip"
