"""新手引导的状态模型。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

StepStatus = Literal["pending", "done", "failed"]
OnboardingStep = Literal["install", "credentials", "first_message", "complete"]


class StepState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: StepStatus = "pending"
    message: str | None = None


class OnboardingState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1] = 1
    current_step: OnboardingStep = "install"
    install: StepState = Field(default_factory=StepState)
    credentials: StepState = Field(default_factory=StepState)
    first_message: StepState = Field(default_factory=StepState)
    tool_id: str | None = None
    profile_id: str | None = None
    project_dir: str | None = None
    updated_at: datetime

    @field_validator("updated_at")
    @classmethod
    def _aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("时间必须带时区")
        return value


class OnboardingUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_id: str | None = None
    profile_id: str | None = None
    project_dir: str | None = None
    reset: bool = False


class OnboardingView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_step: OnboardingStep
    install: StepState
    credentials: StepState
    first_message: StepState
    tool_id: str | None
    profile_id: str | None
    project_dir: str | None
    updated_at: datetime
    chat_url: str
    compliance_note: str
