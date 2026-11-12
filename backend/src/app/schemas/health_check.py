"""档案体检 API 契约。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

HealthCheckStatus = Literal[
    "CONNECTED",
    "INVALID_CREDENTIALS",
    "INVALID_ADDRESS",
    "MODEL_NOT_FOUND",
    "TIMEOUT",
    "RATE_LIMITED",
    "SECRET_MISSING",
    "SECRET_STORE_ERROR",
    "MODEL_REQUIRED",
    "UNKNOWN",
]


class HealthCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str | None = None

    @field_validator("model")
    @classmethod
    def _normalize_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("模型标识不能为空")
        return normalized


class HealthCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    profile_id: str
    model: str | None
    status: HealthCheckStatus
    attempted: bool
    duration_ms: int | None
    message: str
    checked_at: datetime

    @field_validator("checked_at")
    @classmethod
    def _validate_checked_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("时间必须带时区")
        return value
