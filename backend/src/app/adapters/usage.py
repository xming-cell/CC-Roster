"""只读解析 Claude / Codex 会话里的 usage 记录。

不是账单: 只提取 token 计数, 价格由上层内置表估算。未知字段跳过并计数。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class UsageEntry:
    timestamp: datetime
    model: str | None
    input_tokens: int
    output_tokens: int
    calls: int = 1


@dataclass(frozen=True, slots=True)
class UsageScan:
    entries: tuple[UsageEntry, ...]
    skipped: int


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _int(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int) and value >= 0:
        return value
    return 0


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def _iter_lines(path: Path) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    skipped = 0
    try:
        handle = path.open("r", encoding="utf-8-sig", errors="replace")
    except OSError:
        return [], 1
    with handle:
        for line in handle:
            text = line.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                skipped += 1
                continue
            if isinstance(parsed, dict):
                rows.append(parsed)
            else:
                skipped += 1
    return rows, skipped


class ClaudeUsageSource:
    def __init__(self, config_dir: Path) -> None:
        self._root = config_dir / "projects"

    def scan(self) -> UsageScan:
        entries: list[UsageEntry] = []
        skipped = 0
        if not self._root.is_dir():
            return UsageScan((), 0)
        for path in sorted(self._root.glob("*/*.jsonl")):
            rows, line_skips = _iter_lines(path)
            skipped += line_skips
            fallback_time = _file_mtime(path)
            for item in rows:
                if item.get("type") != "assistant":
                    continue
                message = item.get("message")
                if not isinstance(message, dict):
                    skipped += 1
                    continue
                usage = message.get("usage")
                if not isinstance(usage, dict):
                    skipped += 1
                    continue
                input_tokens = (
                    _int(usage.get("input_tokens"))
                    + _int(usage.get("cache_creation_input_tokens"))
                    + _int(usage.get("cache_read_input_tokens"))
                )
                output_tokens = _int(usage.get("output_tokens"))
                if input_tokens == 0 and output_tokens == 0:
                    skipped += 1
                    continue
                model = message.get("model")
                entries.append(
                    UsageEntry(
                        timestamp=_timestamp(item.get("timestamp")) or fallback_time,
                        model=model if isinstance(model, str) and model else None,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                )
        return UsageScan(tuple(entries), skipped)


class CodexUsageSource:
    def __init__(self, config_dir: Path) -> None:
        self._root = config_dir / "sessions"

    def scan(self) -> UsageScan:
        entries: list[UsageEntry] = []
        skipped = 0
        if not self._root.is_dir():
            return UsageScan((), 0)
        for path in sorted(self._root.rglob("*.jsonl")):
            rows, line_skips = _iter_lines(path)
            skipped += line_skips
            fallback_time = _file_mtime(path)
            model: str | None = None
            for item in rows:
                payload = item.get("payload")
                if not isinstance(payload, dict):
                    continue
                if item.get("type") == "turn_context":
                    candidate = payload.get("model")
                    if isinstance(candidate, str) and candidate:
                        model = candidate
                    continue
                if item.get("type") != "event_msg" or payload.get("type") != "token_count":
                    continue
                info = payload.get("info")
                if not isinstance(info, dict):
                    skipped += 1
                    continue
                usage = info.get("last_token_usage")
                if not isinstance(usage, dict):
                    usage = info.get("total_token_usage")
                if not isinstance(usage, dict):
                    skipped += 1
                    continue
                input_tokens = _int(usage.get("input_tokens"))
                output_tokens = _int(usage.get("output_tokens"))
                if input_tokens == 0 and output_tokens == 0:
                    skipped += 1
                    continue
                entries.append(
                    UsageEntry(
                        timestamp=_timestamp(item.get("timestamp")) or fallback_time,
                        model=model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                    )
                )
        return UsageScan(tuple(entries), skipped)
