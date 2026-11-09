"""工具发现的响应模型。

`ToolView` 是列表与详情共用的只读视图; 失败信息一律放在 `warnings` 里,
不通过裸 dict / Any 传递。时间字段由 Pydantic 序列化为带时区的 ISO 8601。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.adapters.base import ToolCapabilities, ToolWarning

ToolStatus = Literal["ok", "unconfigured", "error"]


class ToolView(BaseModel):
    """单个工具的现状; 解析失败时仍保留已读出的字段, 由 warnings 说明原因。"""

    id: str
    display_name: str
    status: ToolStatus
    installed: bool
    configured: bool
    version: str | None = None
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    is_third_party: bool | None = None
    config_path: str | None = None
    last_modified: datetime | None = None
    has_secret: bool = False
    secret_preview: str | None = None
    warnings: list[ToolWarning] = Field(default_factory=list)
    capabilities: ToolCapabilities = Field(default_factory=ToolCapabilities)


class ToolListResponse(BaseModel):
    """列表响应; `warnings` 只承载无法归属到单个工具的降级原因。"""

    tools: list[ToolView] = Field(default_factory=list)
    warnings: list[ToolWarning] = Field(default_factory=list)
