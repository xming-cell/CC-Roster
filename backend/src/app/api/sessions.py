"""会话回放 API; 只读, 所有查询参数在这里校验后转发 service。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi import Path as ApiPath

from app.adapters.registry import build_registry
from app.schemas.session import SessionListResponse, SessionMessagesResponse
from app.services.session_service import SessionService

router = APIRouter(tags=["sessions"])

DEFAULT_LIMIT = 20
MAX_LIMIT = 200
DEFAULT_MESSAGE_LIMIT = 100
MAX_MESSAGE_LIMIT = 500


def get_session_service() -> SessionService:
    return SessionService(build_registry())


SessionServiceDep = Annotated[SessionService, Depends(get_session_service)]
Cursor = Annotated[int, Query(ge=0)]


@router.get("/api/sessions")
def list_sessions(
    service: SessionServiceDep,
    tool_id: str | None = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    cursor: Cursor = 0,
) -> SessionListResponse:
    return service.list_sessions(tool_id=tool_id, limit=limit, cursor=cursor)


@router.get("/api/sessions/{tool_id}/{session_id}")
def read_session(
    tool_id: Annotated[str, ApiPath(min_length=1, max_length=120)],
    session_id: Annotated[str, ApiPath(min_length=1, max_length=255)],
    service: SessionServiceDep,
    limit: Annotated[int, Query(ge=1, le=MAX_MESSAGE_LIMIT)] = DEFAULT_MESSAGE_LIMIT,
    cursor: Cursor = 0,
) -> SessionMessagesResponse:
    return service.read_session(tool_id, session_id, limit=limit, cursor=cursor)
