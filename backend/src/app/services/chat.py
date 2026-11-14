"""应用内对话用例: 上下文、SSE 事件、中断与错误恢复。"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from pathlib import Path

from app.core.clock import utc_now
from app.core.errors import AppError
from app.core.redaction import redact_text
from app.repositories.chat import ChatRepository
from app.schemas.chat import (
    ChatCancelResponse,
    ChatCreateRequest,
    ChatEvent,
    ChatMessage,
    ChatSendRequest,
    ChatSession,
    ChatSessionListResponse,
    ChatSessionView,
    ChatStatus,
    ChatStore,
)
from app.schemas.launcher import LaunchPreview, LaunchRequest
from app.services.chat_executor import ChatExecutor
from app.services.launcher import LaunchService

MAX_LISTED_SESSIONS = 50


class ChatService:
    def __init__(
        self,
        repository: ChatRepository,
        launcher: LaunchService,
        executor: ChatExecutor,
    ) -> None:
        self._repository = repository
        self._launcher = launcher
        self._executor = executor

    def list_sessions(self) -> ChatSessionListResponse:
        sessions = sorted(
            self._repository.load().sessions,
            key=lambda item: item.updated_at,
            reverse=True,
        )[:MAX_LISTED_SESSIONS]
        return ChatSessionListResponse(sessions=[_view(session) for session in sessions])

    def get_session(self, session_id: str) -> ChatSessionView:
        return _view(self._find(session_id))

    def create_session(self, payload: ChatCreateRequest) -> ChatSessionView:
        self._validate_context(payload)
        now = utc_now()
        session = ChatSession(
            id=str(uuid.uuid4()),
            tool_id=payload.tool_id,
            profile_id=payload.profile_id,
            project_dir=payload.project_dir,
            title=payload.title or "新对话",
            status="idle",
            messages=[],
            created_at=now,
            updated_at=now,
        )
        self._repository.mutate(lambda store: store.sessions.append(session))
        return _view(session)

    def ensure_sendable(self, session_id: str) -> None:
        session = self._find(session_id)
        if session.status == "running":
            raise AppError("CHAT_BUSY", "这个对话正在执行, 请先停止或等待完成", 409)
        self._validate_context(
            ChatCreateRequest(
                tool_id=session.tool_id,
                profile_id=session.profile_id,
                project_dir=session.project_dir,
            )
        )

    def stream_message(self, session_id: str, payload: ChatSendRequest) -> Iterator[ChatEvent]:
        session = self._find(session_id)
        if session.status == "running":
            raise AppError("CHAT_BUSY", "这个对话正在执行, 请先停止或等待完成", 409)
        preview = self._validate_context(
            ChatCreateRequest(
                tool_id=session.tool_id,
                profile_id=session.profile_id,
                project_dir=session.project_dir,
            )
        )
        env = self._launcher.environment(
            LaunchRequest(
                tool_id=session.tool_id,
                profile_id=session.profile_id,
                project_dir=session.project_dir,
                model=preview.model,
            )
        )
        user_message = ChatMessage(
            id=str(uuid.uuid4()),
            role="user",
            content=payload.content,
            created_at=utc_now(),
        )
        self._update(session_id, lambda item: _append(item, user_message, "running"))
        yield ChatEvent(type="status", status="running", message="已发送, 等待工具响应")

        command = build_chat_command(
            session.tool_id, preview.executable or "", preview.model, payload.content
        )
        assistant_parts: list[str] = []
        finished = False
        error_message: str | None = None
        tool_count = 0
        try:
            for raw in self._executor.stream(
                session_id=session_id,
                command=command,
                cwd=Path(session.project_dir),
                env=env,
            ):
                if raw.type == "token":
                    assistant_parts.append(raw.content)
                    yield ChatEvent(type="token", content=redact_text(raw.content))
                elif raw.type == "tool":
                    tool_count += 1
                    tool_message = ChatMessage(
                        id=str(uuid.uuid4()),
                        role="tool",
                        content=raw.content or "(无输出)",
                        tool_name=raw.tool_name,
                        created_at=utc_now(),
                    )
                    self._append_running(session_id, tool_message)
                    yield ChatEvent(
                        type="tool",
                        content=redact_text(raw.content or ""),
                        tool_name=raw.tool_name,
                    )
                elif raw.type == "status":
                    yield ChatEvent(type="status", status="running", message=raw.message or "")
                elif raw.type == "error":
                    error_message = raw.message or "工具报告了错误"
                    yield ChatEvent(type="error", message=redact_text(error_message))
            if self._executor.was_cancelled(session_id):
                self._finish(session_id, assistant_parts, "cancelled", None)
                finished = True
                yield ChatEvent(type="cancelled", status="cancelled", message="已停止")
                return
            self._finish(
                session_id, assistant_parts, "failed" if error_message else "idle", error_message
            )
            finished = True
            if error_message is None:
                yield ChatEvent(
                    type="done",
                    status="idle",
                    message=f"完成, 共 {tool_count} 次工具调用" if tool_count else "完成",
                )
        except AppError as exc:
            self._finish(session_id, assistant_parts, "failed", exc.message)
            finished = True
            yield ChatEvent(type="error", message=redact_text(exc.message))
        except Exception as exc:
            message = f"执行失败: {type(exc).__name__}"
            self._finish(session_id, assistant_parts, "failed", message)
            finished = True
            yield ChatEvent(type="error", message=message)
        finally:
            if not finished:
                self._finish(session_id, assistant_parts, "failed", "连接中断")

    def cancel(self, session_id: str) -> ChatCancelResponse:
        session = self._find(session_id)
        cancelled = self._executor.cancel(session_id)
        if cancelled:
            self._update(session_id, lambda item: _set_status(item, "cancelled"))
            return ChatCancelResponse(cancelled=True, message="已发送停止请求")
        if session.status == "running":
            self._update(session_id, lambda item: _set_status(item, "cancelled"))
        return ChatCancelResponse(cancelled=False, message="没有正在运行的工具进程")

    def _validate_context(self, payload: ChatCreateRequest) -> LaunchPreview:
        project = Path(payload.project_dir)
        if not project.exists() or not project.is_dir():
            raise AppError("CHAT_CONTEXT_INVALID", "项目目录不存在或不是目录", 400)
        preview = self._launcher.preview(
            LaunchRequest(
                tool_id=payload.tool_id,
                profile_id=payload.profile_id,
                project_dir=payload.project_dir,
            )
        )
        if not preview.can_launch:
            message = "; ".join(blocker.message for blocker in preview.blockers)
            raise AppError("CHAT_CONTEXT_INVALID", message or "对话上下文不可用", 400)
        return preview

    def _find(self, session_id: str) -> ChatSession:
        session = self._repository.get(session_id)
        if session is None:
            raise AppError("CHAT_SESSION_NOT_FOUND", "对话不存在", 404)
        return session

    def _update(self, session_id: str, change: Callable[[ChatSession], None]) -> None:
        self._repository.mutate(lambda store: change(_require(store, session_id)))

    def _append_running(self, session_id: str, message: ChatMessage) -> None:
        def change(item: ChatSession) -> None:
            _append(item, message, "running")

        self._update(session_id, change)

    def _finish(
        self,
        session_id: str,
        parts: list[str],
        status: ChatStatus,
        error: str | None,
    ) -> None:
        now = utc_now()
        content = "".join(parts).strip()
        messages: list[ChatMessage] = []
        if content:
            messages.append(
                ChatMessage(
                    id=str(uuid.uuid4()),
                    role="assistant",
                    content=content,
                    created_at=now,
                    is_error=status == "failed",
                )
            )
        if error:
            messages.append(
                ChatMessage(
                    id=str(uuid.uuid4()),
                    role="system",
                    content=error,
                    created_at=now,
                    is_error=True,
                )
            )

        def change(item: ChatSession) -> None:
            item.messages.extend(messages)
            item.status = status
            item.updated_at = now

        self._repository.mutate(lambda store: change(_require(store, session_id)))


def _view(session: ChatSession) -> ChatSessionView:
    return ChatSessionView.model_validate(session.model_dump())


def _append(session: ChatSession, message: ChatMessage, status: ChatStatus) -> None:
    session.messages.append(message)
    session.status = status
    session.updated_at = message.created_at
    if session.title == "新对话" and message.role == "user":
        session.title = message.content[:40]


def _set_status(session: ChatSession, status: ChatStatus) -> None:
    session.status = status
    session.updated_at = utc_now()


def _require(store: ChatStore, session_id: str) -> ChatSession:
    for session in store.sessions:
        if session.id == session_id:
            return session
    raise AppError("CHAT_SESSION_NOT_FOUND", "对话不存在", 404)


def build_chat_command(tool_id: str, executable: str, model: str | None, prompt: str) -> list[str]:
    if tool_id == "claude-code":
        return [executable, "-p", prompt, "--output-format", "stream-json", "--verbose"]
    if tool_id == "codex-cli":
        command = [executable, "exec", "--json"]
        if model:
            command.extend(["--model", model])
        command.append(prompt)
        return command
    raise AppError("CHAT_UNSUPPORTED", f"{tool_id} 不支持应用内对话", 400)
