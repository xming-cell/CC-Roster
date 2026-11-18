"""018 群聊对比: 并发、独立超时 / 失败隔离、取消与限频。"""

from __future__ import annotations

import threading
import time
from collections.abc import Sequence
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import UTC, datetime
from pathlib import Path

from app.core.errors import AppError
from app.schemas.group_chat import (
    GroupCancelResponse,
    GroupChatRequest,
    GroupChatResponse,
    GroupChatResult,
    GroupParticipant,
)
from app.schemas.launcher import LaunchRequest
from app.services.chat import build_chat_command
from app.services.chat_executor import ChatExecutor
from app.services.launcher import LaunchService

_RATE_LOCK = threading.Lock()
_LAST_STARTED: dict[str, float] = {}


class GroupChatService:
    def __init__(
        self,
        launcher: LaunchService,
        executor: ChatExecutor,
        *,
        max_workers: int = 4,
        min_interval_seconds: float = 1.0,
    ) -> None:
        self._launcher = launcher
        self._executor = executor
        self._max_workers = max_workers
        self._min_interval = min_interval_seconds
        self._active: dict[str, list[str]] = {}
        self._active_lock = threading.Lock()

    def run(self, request: GroupChatRequest) -> GroupChatResponse:
        self._check_rate_limit()
        started = time.monotonic()
        results: list[GroupChatResult | None] = [None] * len(request.participants)
        ready: dict[int, tuple[list[str], dict[str, str]]] = {}
        for index, participant in enumerate(request.participants):
            try:
                preview = self._launcher.preview(
                    LaunchRequest(
                        tool_id=participant.tool_id,
                        profile_id=participant.profile_id,
                        project_dir=request.project_dir,
                        model=participant.model,
                    )
                )
                if not preview.can_launch:
                    message = "; ".join(blocker.message for blocker in preview.blockers)
                    results[index] = _failed(participant, message)
                    continue
                env = self._launcher.environment(
                    LaunchRequest(
                        tool_id=participant.tool_id,
                        profile_id=participant.profile_id,
                        project_dir=request.project_dir,
                        model=preview.model,
                    )
                )
                command = build_chat_command(
                    participant.tool_id,
                    preview.executable or "",
                    preview.model,
                    request.question,
                )
                ready[index] = (command, env)
            except AppError as exc:
                results[index] = _failed(participant, exc.message)

        session_ids = {index: f"{request.group_id}:{index}" for index in ready}
        with self._active_lock:
            self._active[request.group_id] = list(session_ids.values())
        try:
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures: dict[Future[GroupChatResult], int] = {}
                for index, (command, env) in ready.items():
                    future = pool.submit(
                        self._run_one,
                        request,
                        request.participants[index],
                        session_ids[index],
                        command,
                        env,
                    )
                    futures[future] = index
                done, not_done = wait(futures, timeout=request.timeout_seconds)
                for future in not_done:
                    index = futures[future]
                    self._executor.cancel(session_ids[index])
                    results[index] = _timeout(
                        request.participants[index],
                        int((time.monotonic() - started) * 1000),
                    )
                for future in done:
                    index = futures[future]
                    try:
                        results[index] = future.result()
                    except Exception as exc:
                        results[index] = _failed(
                            request.participants[index],
                            f"执行失败: {type(exc).__name__}",
                        )
        finally:
            with self._active_lock:
                self._active.pop(request.group_id, None)

        return GroupChatResponse(
            group_id=request.group_id,
            question=request.question,
            results=[item for item in results if item is not None],
            completed_at=datetime.now(UTC),
        )

    def cancel(self, group_id: str) -> GroupCancelResponse:
        with self._active_lock:
            session_ids = list(self._active.get(group_id, []))
        cancelled = any(self._executor.cancel(session_id) for session_id in session_ids)
        return GroupCancelResponse(
            cancelled=cancelled,
            message="已发送取消请求" if cancelled else "没有正在运行的群聊进程",
        )

    def _run_one(
        self,
        request: GroupChatRequest,
        participant: GroupParticipant,
        session_id: str,
        command: Sequence[str],
        env: dict[str, str],
    ) -> GroupChatResult:
        started = time.monotonic()
        parts: list[str] = []
        error: str | None = None
        try:
            for raw in self._executor.stream(
                session_id=session_id,
                command=command,
                cwd=Path(request.project_dir),
                env=env,
            ):
                if raw.type == "token":
                    parts.append(raw.content)
                elif raw.type == "error":
                    error = raw.message or "工具报告了错误"
        except Exception as exc:
            error = f"执行失败: {type(exc).__name__}"
        duration = int((time.monotonic() - started) * 1000)
        if error is not None:
            return GroupChatResult(
                tool_id=participant.tool_id,
                profile_id=participant.profile_id,
                model=participant.model,
                status="failed",
                content="".join(parts),
                error=error,
                duration_ms=duration,
            )
        return GroupChatResult(
            tool_id=participant.tool_id,
            profile_id=participant.profile_id,
            model=participant.model,
            status="success",
            content="".join(parts),
            duration_ms=duration,
        )

    def _check_rate_limit(self) -> None:
        if self._min_interval <= 0:
            return
        with _RATE_LOCK:
            now = time.monotonic()
            previous = _LAST_STARTED.get("group")
            if previous is not None and now - previous < self._min_interval:
                raise AppError(
                    "GROUP_RATE_LIMITED",
                    "群聊请求过于频繁, 请稍后再试",
                    429,
                )
            _LAST_STARTED["group"] = now


def _failed(participant: GroupParticipant, message: str) -> GroupChatResult:
    return GroupChatResult(
        tool_id=participant.tool_id,
        profile_id=participant.profile_id,
        model=participant.model,
        status="failed",
        error=message,
        duration_ms=0,
    )


def _timeout(participant: GroupParticipant, duration_ms: int) -> GroupChatResult:
    return GroupChatResult(
        tool_id=participant.tool_id,
        profile_id=participant.profile_id,
        model=participant.model,
        status="timeout",
        error="执行超时, 已停止该参与者",
        duration_ms=duration_ms,
    )
