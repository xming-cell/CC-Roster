"""Claude Code / Codex CLI 的只读会话源。

两边格式不同, 但都落成同一个 `SessionMessage` 序列。本模块只读文件:
不创建目录、不改 mtime、不把原始内容写进应用数据库。
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from app.adapters.base import ToolWarning
from app.schemas.session import SessionMessage, SessionRole, SessionSummary

_MAX_TITLE_LENGTH = 80
_SUMMARY_CACHE: dict[str, tuple[int, int, SessionSummary]] = {}
_SUMMARY_LOCK = threading.Lock()


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _str(value: object) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _file_mtime(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)


def _first_text(value: object) -> str:
    """把 Claude / Codex 的内容块拼成一段可读文本。"""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        value = [value]
    parts: list[str] = []
    for block in _list(value):
        item = _dict(block)
        for key in ("text", "input_text", "output_text", "content"):
            text = _str(item.get(key))
            if text is not None:
                parts.append(text)
                break
    return "\n".join(parts).strip()


def _title_from(text: str) -> str:
    normalized = " ".join(text.split())
    if not normalized:
        return "未命名会话"
    return normalized[:_MAX_TITLE_LENGTH]


def _warning(
    code: Literal["PARSE_ERROR", "PERMISSION_DENIED", "UNKNOWN_FORMAT"], message: str
) -> ToolWarning:
    return ToolWarning(code=code, message=message)


class _SessionBase:
    def __init__(self, root: Path, tool_id: str) -> None:
        self._root = root
        self._tool_id = tool_id

    def _files(self) -> dict[str, Path]:
        raise NotImplementedError

    def list_summaries(self) -> tuple[list[SessionSummary], list[ToolWarning]]:
        summaries: list[SessionSummary] = []
        warnings: list[ToolWarning] = []
        for session_id, path in self._files().items():
            try:
                summary, file_warnings = self._summary(session_id, path)
            except OSError:
                warnings.append(_warning("PERMISSION_DENIED", f"会话文件无法读取: {path.name}"))
                continue
            summaries.append(summary)
            warnings.extend(file_warnings)
        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        return summaries, warnings

    def read_messages(
        self,
        session_id: str,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[SessionMessage], bool, list[ToolWarning]]:
        path = self._files().get(session_id)
        if path is None:
            raise FileNotFoundError(session_id)
        messages: list[SessionMessage] = []
        warnings: list[ToolWarning] = []
        has_more = False
        for index, message, warning in self._iter_messages(path):
            if warning is not None:
                warnings.append(warning)
            if message is None:
                continue
            if index < offset:
                continue
            if len(messages) >= limit:
                has_more = True
                break
            messages.append(message)
        return messages, has_more, warnings

    def _summary(self, session_id: str, path: Path) -> tuple[SessionSummary, list[ToolWarning]]:
        raise NotImplementedError

    def _iter_messages(
        self, path: Path
    ) -> Iterator[tuple[int, SessionMessage | None, ToolWarning | None]]:
        raise NotImplementedError

    def _cached_summary(
        self, path: Path, build: object
    ) -> tuple[SessionSummary, list[ToolWarning]]:
        # build is callable; keep the signature explicit for mypy.
        raise NotImplementedError

    def _read_summary_cache(self, path: Path) -> SessionSummary | None:
        try:
            stat = path.stat()
        except OSError:
            return None
        key = str(path)
        with _SUMMARY_LOCK:
            cached = _SUMMARY_CACHE.get(key)
        if cached is not None and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2]
        return None

    def _write_summary_cache(self, path: Path, summary: SessionSummary) -> None:
        try:
            stat = path.stat()
        except OSError:
            return
        with _SUMMARY_LOCK:
            _SUMMARY_CACHE[str(path)] = (stat.st_mtime_ns, stat.st_size, summary)


def _iter_json_lines(path: Path) -> Iterator[tuple[int, dict[str, object] | None]]:
    """逐行读取; 坏行返回 None, 由调用方转成 warning。"""
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        for number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                yield number, None
                continue
            yield number, parsed if isinstance(parsed, dict) else None


class ClaudeSessionSource(_SessionBase):
    def __init__(self, config_dir: Path) -> None:
        super().__init__(config_dir / "projects", "claude-code")

    def _files(self) -> dict[str, Path]:
        if not self._root.is_dir():
            return {}
        result: dict[str, Path] = {}
        for path in sorted(self._root.glob("*/*.jsonl")):
            if path.is_file():
                result[path.stem] = path
        return result

    def _summary(self, session_id: str, path: Path) -> tuple[SessionSummary, list[ToolWarning]]:
        cached = self._read_summary_cache(path)
        if cached is not None:
            return cached, []
        warnings: list[ToolWarning] = []
        title = "未命名会话"
        project_path: str | None = None
        started_at: datetime | None = None
        for number, item in _iter_json_lines(path):
            if item is None:
                warnings.append(_warning("PARSE_ERROR", f"第 {number} 行不是合法 JSON"))
                continue
            if project_path is None:
                project_path = _str(item.get("cwd"))
            if started_at is None:
                started_at = _timestamp(item.get("timestamp"))
            if title == "未命名会话" and item.get("type") == "user":
                title = _title_from(_first_text(_dict(item.get("message")).get("content")))
            if title != "未命名会话" and project_path is not None and started_at is not None:
                break
        summary = SessionSummary(
            id=session_id,
            tool_id=self._tool_id,
            title=title,
            project_path=project_path,
            started_at=started_at or _file_mtime(path),
            updated_at=_file_mtime(path),
            warnings=warnings,
        )
        self._write_summary_cache(path, summary)
        return summary, warnings

    def _iter_messages(
        self, path: Path
    ) -> Iterator[tuple[int, SessionMessage | None, ToolWarning | None]]:
        index = 0
        for number, item in _iter_json_lines(path):
            if item is None:
                yield index, None, _warning("PARSE_ERROR", f"第 {number} 行不是合法 JSON")
                continue
            raw_type = _str(item.get("type")) or "unknown"
            for message in _claude_messages(item, number, raw_type):
                yield index, message, None
                index += 1


class CodexSessionSource(_SessionBase):
    def __init__(self, config_dir: Path) -> None:
        super().__init__(config_dir / "sessions", "codex-cli")

    def _files(self) -> dict[str, Path]:
        if not self._root.is_dir():
            return {}
        result: dict[str, Path] = {}
        for path in sorted(self._root.rglob("*.jsonl")):
            if path.is_file():
                result[path.stem] = path
        return result

    def _summary(self, session_id: str, path: Path) -> tuple[SessionSummary, list[ToolWarning]]:
        cached = self._read_summary_cache(path)
        if cached is not None:
            return cached, []
        warnings: list[ToolWarning] = []
        title = "未命名会话"
        project_path: str | None = None
        started_at: datetime | None = None
        seen = 0
        for number, item in _iter_json_lines(path):
            seen += 1
            if item is None:
                warnings.append(_warning("PARSE_ERROR", f"第 {number} 行不是合法 JSON"))
                continue
            payload = _dict(item.get("payload"))
            if item.get("type") == "session_meta":
                project_path = _str(payload.get("cwd")) or project_path
                started_at = _timestamp(payload.get("timestamp")) or started_at
            if (
                title == "未命名会话"
                and item.get("type") == "response_item"
                and payload.get("type") == "message"
                and payload.get("role") == "user"
            ):
                title = _title_from(_first_text(payload.get("content")))
            if seen >= 8 and title != "未命名会话":
                break
        summary = SessionSummary(
            id=session_id,
            tool_id=self._tool_id,
            title=title,
            project_path=project_path,
            started_at=started_at or _file_mtime(path),
            updated_at=_file_mtime(path),
            warnings=warnings,
        )
        self._write_summary_cache(path, summary)
        return summary, warnings

    def _iter_messages(
        self, path: Path
    ) -> Iterator[tuple[int, SessionMessage | None, ToolWarning | None]]:
        index = 0
        for number, item in _iter_json_lines(path):
            if item is None:
                yield index, None, _warning("PARSE_ERROR", f"第 {number} 行不是合法 JSON")
                continue
            raw_type = _str(item.get("type")) or "unknown"
            for message in _codex_messages(item, number, raw_type):
                yield index, message, None
                index += 1


def _message(
    *,
    identifier: str,
    role: SessionRole,
    timestamp: datetime | None,
    content: str,
    raw_type: str,
    tool_name: str | None = None,
    is_error: bool = False,
) -> SessionMessage:
    return SessionMessage(
        id=identifier,
        role=role,
        timestamp=timestamp,
        content=content,
        tool_name=tool_name,
        is_error=is_error,
        raw_type=raw_type,
    )


def _claude_messages(item: dict[str, object], number: int, raw_type: str) -> list[SessionMessage]:
    timestamp = _timestamp(item.get("timestamp"))
    identifier = _str(item.get("uuid")) or f"line-{number}"
    kind = raw_type
    message = _dict(item.get("message"))
    blocks = message.get("content")
    if kind not in {"user", "assistant"}:
        if kind in {"summary", "system"}:
            text = _first_text(blocks) or _str(item.get("summary")) or ""
            if text:
                return [
                    _message(
                        identifier=identifier,
                        role="system",
                        timestamp=timestamp,
                        content=text,
                        raw_type=kind,
                    )
                ]
        return []
    role: SessionRole = "user" if kind == "user" else "assistant"
    result: list[SessionMessage] = []
    if isinstance(blocks, str):
        text = blocks.strip()
        if text:
            result.append(
                _message(
                    identifier=identifier,
                    role=role,
                    timestamp=timestamp,
                    content=text,
                    raw_type=kind,
                )
            )
        return result
    for block_index, raw_block in enumerate(_list(blocks)):
        block = _dict(raw_block)
        block_type = _str(block.get("type")) or "text"
        block_id = f"{identifier}-{block_index}"
        if block_type == "tool_use":
            result.append(
                _message(
                    identifier=block_id,
                    role="tool_call",
                    timestamp=timestamp,
                    content=_tool_call_text(block.get("name"), block.get("input")),
                    raw_type="tool_use",
                    tool_name=_str(block.get("name")),
                )
            )
        elif block_type == "tool_result":
            result.append(
                _message(
                    identifier=block_id,
                    role="tool_result",
                    timestamp=timestamp,
                    content=_first_text(block.get("content")) or "(无输出)",
                    raw_type="tool_result",
                    is_error=bool(block.get("is_error")),
                )
            )
        else:
            text = _first_text(block)
            if text:
                result.append(
                    _message(
                        identifier=block_id,
                        role=role,
                        timestamp=timestamp,
                        content=text,
                        raw_type=block_type,
                    )
                )
    return result


def _codex_messages(item: dict[str, object], number: int, raw_type: str) -> list[SessionMessage]:
    if raw_type != "response_item":
        return []
    timestamp = _timestamp(item.get("timestamp"))
    payload = _dict(item.get("payload"))
    payload_type = _str(payload.get("type")) or "unknown"
    identifier = f"line-{number}"
    if payload_type == "message":
        role: SessionRole = "user" if payload.get("role") == "user" else "assistant"
        text = _first_text(payload.get("content"))
        return (
            [
                _message(
                    identifier=identifier,
                    role=role,
                    timestamp=timestamp,
                    content=text,
                    raw_type=payload_type,
                )
            ]
            if text
            else []
        )
    if payload_type == "function_call":
        return [
            _message(
                identifier=_str(payload.get("call_id")) or identifier,
                role="tool_call",
                timestamp=timestamp,
                content=_tool_call_text(payload.get("name"), payload.get("arguments")),
                raw_type=payload_type,
                tool_name=_str(payload.get("name")),
            )
        ]
    if payload_type == "function_call_output":
        return [
            _message(
                identifier=_str(payload.get("call_id")) or identifier,
                role="tool_result",
                timestamp=timestamp,
                content=_str(payload.get("output")) or "(无输出)",
                raw_type=payload_type,
            )
        ]
    if payload_type == "reasoning":
        text = _first_text(payload.get("summary")) or _first_text(payload.get("content"))
        return (
            [
                _message(
                    identifier=identifier,
                    role="system",
                    timestamp=timestamp,
                    content=text,
                    raw_type=payload_type,
                )
            ]
            if text
            else []
        )
    return [
        _message(
            identifier=identifier,
            role="unknown",
            timestamp=timestamp,
            content=f"[未识别事件] {payload_type}",
            raw_type=payload_type,
        )
    ]


def _tool_call_text(name: object, arguments: object) -> str:
    label = _str(name) or "unknown"
    if isinstance(arguments, str):
        return f"{label}\n{arguments}"
    if arguments is None:
        return label
    try:
        return f"{label}\n{json.dumps(arguments, ensure_ascii=False, sort_keys=True)[:4000]}"
    except (TypeError, ValueError):
        return label


def session_id_is_safe(value: str) -> bool:
    return bool(value) and all(character.isalnum() or character in "._-" for character in value)
