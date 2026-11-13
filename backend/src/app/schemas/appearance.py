"""好友外观覆盖的持久化与 API 模型。"""

from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr, field_validator, model_validator

APPEARANCE_SCHEMA_VERSION: Final[Literal[1]] = 1
BubblePreset = Literal["soft", "rounded", "compact"]


def _validate_color(value: str | None) -> str | None:
    if value is not None and (
        len(value) != 7
        or value[0] != "#"
        or any(character not in "0123456789abcdefABCDEF" for character in value[1:])
    ):
        raise ValueError("颜色必须是 #RRGGBB 格式")
    return value.upper() if value is not None else None


class AppearanceOverride(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accent_color: StrictStr | None = None
    background_color: StrictStr | None = None
    bubble_preset: BubblePreset | None = None

    @field_validator("accent_color", "background_color")
    @classmethod
    def validate_color(cls, value: str | None) -> str | None:
        return _validate_color(value)

    @model_validator(mode="after")
    def require_override(self) -> "AppearanceOverride":
        if all(
            value is None
            for value in (self.accent_color, self.background_color, self.bubble_preset)
        ):
            raise ValueError("至少需要设置一项外观覆盖")
        return self


class AppearanceStore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = APPEARANCE_SCHEMA_VERSION
    appearances: dict[str, AppearanceOverride] = Field(default_factory=dict)


class AppearanceListResponse(AppearanceStore):
    pass


class AppearanceView(AppearanceOverride):
    tool_id: str


class AppearanceResetResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str
    reset: bool = True
