"""运行期设置: 全局只读、快捷键与开机自启。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator


class DesktopCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tray: bool
    hotkey: bool
    autostart: bool


class RuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    read_only: bool = False
    hotkey: str = "ctrl+alt+c"
    autostart: bool = False
    updated_at: datetime


class SettingsView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_only: bool
    hotkey: str
    autostart: bool
    updated_at: datetime
    message: str
    capabilities: DesktopCapabilities

    @field_validator("updated_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("时间必须带时区")
        return value


class SettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    read_only: bool | None = None
    hotkey: str | None = None
    autostart: bool | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "SettingsUpdate":
        if self.read_only is None and self.hotkey is None and self.autostart is None:
            raise ValueError("至少提供一个设置字段")
        return self
