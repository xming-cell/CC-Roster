"""应用内对话 API: 上下文 CRUD + SSE 流 + 取消。"""

from collections.abc import Iterator
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.api.launcher import get_launch_service
from app.core.errors import AppError
from app.core.paths import resolve_data_dir
from app.repositories.chat import ChatRepository
from app.schemas.chat import (
    ChatCancelResponse,
    ChatCreateRequest,
    ChatEvent,
    ChatSendRequest,
    ChatSessionListResponse,
    ChatSessionView,
)
from app.services.chat import ChatService
from app.services.chat_executor import SubprocessChatExecutor

router = APIRouter(tags=["chat"])


def get_chat_service() -> ChatService:
    data_dir = Path(resolve_data_dir())
    return ChatService(
        ChatRepository(data_dir),
        get_launch_service(),
        SubprocessChatExecutor(),
    )


ChatServiceDep = Annotated[ChatService, Depends(get_chat_service)]


@router.get("/api/chat/sessions", response_model=ChatSessionListResponse)
def list_chat_sessions(service: ChatServiceDep) -> ChatSessionListResponse:
    return service.list_sessions()


@router.post("/api/chat/sessions", response_model=ChatSessionView, status_code=201)
def create_chat_session(payload: ChatCreateRequest, service: ChatServiceDep) -> ChatSessionView:
    return service.create_session(payload)


@router.get("/api/chat/sessions/{session_id}", response_model=ChatSessionView)
def get_chat_session(session_id: str, service: ChatServiceDep) -> ChatSessionView:
    return service.get_session(session_id)


@router.post("/api/chat/sessions/{session_id}/messages")
def send_chat_message(
    session_id: str,
    payload: ChatSendRequest,
    service: ChatServiceDep,
) -> StreamingResponse:
    service.get_session(session_id)
    service.ensure_sendable(session_id)

    def events() -> Iterator[str]:
        try:
            for event in service.stream_message(session_id, payload):
                yield _sse(event)
        except AppError as exc:
            yield _sse(ChatEvent(type="error", message=exc.message))

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/api/chat/sessions/{session_id}/cancel", response_model=ChatCancelResponse)
def cancel_chat_message(session_id: str, service: ChatServiceDep) -> ChatCancelResponse:
    return service.cancel(session_id)


def _sse(event: ChatEvent) -> str:
    return f"data: {event.model_dump_json()}\n\n"
