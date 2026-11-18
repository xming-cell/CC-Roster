"""019 用量聚合: 只读会话 usage, 按日期 / 工具 / 模型汇总。"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.adapters.registry import ToolRegistry
from app.adapters.usage import UsageEntry
from app.core.clock import utc_now
from app.core.pricing import NOTE, estimate_cost
from app.schemas.usage import UsageRecord, UsageResponse, UsageTotals, UsageWarning


class UsageService:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def summarize(self, days: int) -> UsageResponse:
        cutoff = utc_now() - timedelta(days=days)
        groups: dict[tuple[str, str, str | None], list[int]] = defaultdict(lambda: [0, 0, 0])
        warnings: list[UsageWarning] = []
        skipped = 0
        for adapter in self._registry.adapters:
            try:
                scan = adapter.usage_scan()
            except Exception as exc:
                warnings.append(
                    UsageWarning(
                        code="USAGE_ADAPTER_ERROR",
                        message=f"{adapter.display_name} 用量读取失败: {type(exc).__name__}",
                    )
                )
                continue
            skipped += scan.skipped
            for entry in scan.entries:
                if not self._in_period(entry, cutoff):
                    continue
                key = (entry.timestamp.astimezone(UTC).date().isoformat(), adapter.id, entry.model)
                groups[key][0] += entry.calls
                groups[key][1] += entry.input_tokens
                groups[key][2] += entry.output_tokens
        return self._response(days, groups, skipped, warnings)

    def _response(
        self,
        days: int,
        groups: dict[tuple[str, str, str | None], list[int]],
        skipped: int,
        warnings: list[UsageWarning],
    ) -> UsageResponse:
        records: list[UsageRecord] = []
        total_calls = total_input = total_output = unknown_calls = 0
        total_cost = Decimal("0")
        unknown_models: set[str] = set()
        for (date, tool_id, model), (calls, input_tokens, output_tokens) in groups.items():
            cost = estimate_cost(model, input_tokens, output_tokens)
            known = cost is not None
            if cost is None:
                unknown_calls += calls
                if model is not None:
                    unknown_models.add(model)
            else:
                total_cost += cost
            records.append(
                UsageRecord(
                    date=date,
                    tool_id=tool_id,
                    model=model,
                    calls=calls,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    estimated_cost=None if cost is None else f"{cost:.6f}",
                    price_known=known,
                )
            )
            total_calls += calls
            total_input += input_tokens
            total_output += output_tokens
        records.sort(key=lambda item: (item.date, item.tool_id, item.model or ""), reverse=True)
        if skipped:
            warnings.append(
                UsageWarning(
                    code="USAGE_SKIPPED",
                    message=f"已跳过 {skipped} 条无法解析的用量记录",
                )
            )
        if unknown_models:
            warnings.append(
                UsageWarning(
                    code="UNKNOWN_PRICE",
                    message="以下模型没有内置价格, 未估算: " + ", ".join(sorted(unknown_models)),
                )
            )
        return UsageResponse(
            days=days,
            records=records,
            totals=UsageTotals(
                calls=total_calls,
                input_tokens=total_input,
                output_tokens=total_output,
                estimated_cost=f"{total_cost:.6f}",
                unknown_price_calls=unknown_calls,
            ),
            pricing_note=NOTE,
            warnings=warnings,
        )

    @staticmethod
    def _in_period(entry: UsageEntry, cutoff: datetime) -> bool:
        return entry.timestamp >= cutoff
