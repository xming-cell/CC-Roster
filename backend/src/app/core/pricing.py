"""内置价格表 (USD / 百万 token)。

只用于估算, 不是供应商账单; 未知模型返回 None, 上层必须标「未知」。
"""

from decimal import Decimal

PRICE_TABLE: dict[str, tuple[Decimal, Decimal]] = {
    "claude-sonnet-4": (Decimal("3"), Decimal("15")),
    "claude-opus-4": (Decimal("15"), Decimal("75")),
    "claude-3-5-haiku": (Decimal("0.8"), Decimal("4")),
    "gpt-5": (Decimal("1.25"), Decimal("10")),
    "gpt-5-codex": (Decimal("1.25"), Decimal("10")),
    "gpt-5-mini": (Decimal("0.25"), Decimal("2")),
}

_MILLION = Decimal("1000000")
_QUANT = Decimal("0.000001")
NOTE = "估算使用应用内置离线价格表 (USD / 百万 token), 不代表供应商账单; 未知模型不估算。"


def estimate_cost(model: str | None, input_tokens: int, output_tokens: int) -> Decimal | None:
    if model is None:
        return None
    price = PRICE_TABLE.get(model)
    if price is None:
        return None
    input_price, output_price = price
    cost = (Decimal(input_tokens) * input_price + Decimal(output_tokens) * output_price) / _MILLION
    return cost.quantize(_QUANT)
