"""被管理工具的子进程执行层。

本层只负责启动 CLI、按行解析事件、终止进程; 不实现 agent 能力。
Claude / Codex 的输出格式未知时降级为文本, 不静默丢弃。
"""

from __future__ import annotations

import json
import os
import subprocess
import threading
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Protocol

from app.core.errors import AppError

RawEventType = Literal["status", "token", "tool", "error"]


@dataclass(frozen=True, slots=True)
class RawChatEvent:
    type: RawEventType
    content: str = ""
    tool_name: str | None = None
    message: str | None = None


class ChatExecutor(Protocol):
    def stream(
        self,
        *,
        session_id: str,
        command: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
    ) -> Iterator[RawChatEvent]: ...

    def cancel(self, session_id: str) -> bool: ...

    def was_cancelled(self, session_id: str) -> bool: ...


_PROCESSES: dict[str, subprocess.Popen[str]] = {}
_CANCELLED: set[str] = set()
_PROCESS_LOCK = threading.Lock()


class SubprocessChatExecutor:
    """真实 CLI 执行器; 进程表是模块级, 便于取消端点跨请求找到子进程。"""

    def __init__(self, platform: str | None = None) -> None:
        self._platform = os.name if platform is None else platform

    def stream(
        self,
        *,
        session_id: str,
        command: Sequence[str],
        cwd: Path,
        env: Mapping[str, str],
    ) -> Iterator[RawChatEvent]:
        argv = subprocess_argv(command, self._platform)
        with _PROCESS_LOCK:
            _CANCELLED.discard(session_id)
        process = subprocess.Popen(
            argv,
            cwd=str(cwd),
            env=dict(env),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        with _PROCESS_LOCK:
            _PROCESSES[session_id] = process
        try:
            assert process.stdout is not None
            for line in process.stdout:
                yield from parse_output_line(line)
            code = process.wait()
            if self.was_cancelled(session_id):
                return
            if code != 0:
                raise AppError("CHAT_PROCESS_FAILED", f"工具进程退出码 {code}", 500)
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    process.kill()
            with _PROCESS_LOCK:
                _PROCESSES.pop(session_id, None)

    def cancel(self, session_id: str) -> bool:
        with _PROCESS_LOCK:
            process = _PROCESSES.get(session_id)
            if process is None or process.poll() is not None:
                return False
            _CANCELLED.add(session_id)
        process.terminate()
        return True

    def was_cancelled(self, session_id: str) -> bool:
        with _PROCESS_LOCK:
            return session_id in _CANCELLED


def subprocess_argv(command: Sequence[str], platform: str) -> list[str]:
    if platform == "nt" or platform == "win32":
        executable = command[0].lower() if command else ""
        if executable.endswith((".cmd", ".bat")):
            return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    return list(command)


def parse_output_line(line: str) -> Iterator[RawChatEvent]:
    text = line.rstrip("\r\n")
    if not text.strip():
        return
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        yield RawChatEvent(type="token", content=text)
        return
    if not isinstance(parsed, dict):
        yield RawChatEvent(type="token", content=text)
        return
    yield from parse_json_event(parsed)


def parse_json_event(event: dict[str, object]) -> Iterator[RawChatEvent]:
    kind = event.get("type")
    if kind == "assistant":
        message = event.get("message")
        if isinstance(message, dict):
            yield from _claude_content(message.get("content"))
        return
    if kind == "result":
        return
    if kind == "system":
        yield RawChatEvent(type="status", message="工具已连接, 正在处理")
        return
    if kind == "item.started":
        item = event.get("item")
        if isinstance(item, dict) and item.get("type") == "command_execution":
            yield RawChatEvent(
                type="tool",
                tool_name="shell",
                content=str(item.get("command") or ""),
            )
            return
    if kind == "item.completed":
        item = event.get("item")
        if isinstance(item, dict):
            if item.get("type") == "agent_message":
                yield RawChatEvent(type="token", content=str(item.get("text") or ""))
                return
            if item.get("type") == "command_execution":
                yield RawChatEvent(
                    type="tool",
                    tool_name="shell",
                    content=str(item.get("aggregated_output") or ""),
                )
                return
    if kind in {"turn.started", "thread.started"}:
        yield RawChatEvent(type="status", message="思考中")
        return
    if kind in {"turn.failed", "error"}:
        message = event.get("message") or event.get("error") or "工具报告了错误"
        yield RawChatEvent(type="error", message=str(message))
        return
    yield RawChatEvent(type="status", message=f"未识别事件: {kind}")


def _claude_content(content: object) -> Iterator[RawChatEvent]:
    if isinstance(content, str):
        yield RawChatEvent(type="token", content=content)
        return
    if not isinstance(content, list):
        return
    for block in content:
        if not isinstance(block, dict):
            continue
        block_type = block.get("type")
        if block_type == "text":
            yield RawChatEvent(type="token", content=str(block.get("text") or ""))
        elif block_type == "tool_use":
            yield RawChatEvent(
                type="tool",
                tool_name=str(block.get("name") or "tool"),
                content=str(block.get("input") or ""),
            )
