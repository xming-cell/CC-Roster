"""用量与估算花费的响应模型; 金额一律字符串。"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class UsageRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: str
    tool_id: str
    model: str | None
    calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost: str | None
    currency: Literal["USD"] = "USD"
    price_known: bool


class UsageTotals(BaseModel):
    model_config = ConfigDict(extra="forbid")

    calls: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost: str
    currency: Literal["USD"] = "USD"
    unknown_price_calls: int = Field(ge=0)


class UsageWarning(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str


class UsageResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    days: int
    records: list[UsageRecord] = Field(default_factory=list)
    totals: UsageTotals
    pricing_note: str
    warnings: list[UsageWarning] = Field(default_factory=list)
