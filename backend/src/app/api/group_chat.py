"""群聊对比 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import Path as ApiPath

from app.api.launcher import get_launch_service
from app.schemas.group_chat import GroupCancelResponse, GroupChatRequest, GroupChatResponse
from app.services.chat_executor import SubprocessChatExecutor
from app.services.group_chat import GroupChatService

router = APIRouter(tags=["group-chat"])


def get_group_chat_service() -> GroupChatService:
    return GroupChatService(get_launch_service(), SubprocessChatExecutor())


GroupChatServiceDep = Annotated[GroupChatService, Depends(get_group_chat_service)]


@router.post("/api/group-chat", response_model=GroupChatResponse)
def run_group_chat(payload: GroupChatRequest, service: GroupChatServiceDep) -> GroupChatResponse:
    return service.run(payload)


@router.post("/api/group-chat/{group_id}/cancel", response_model=GroupCancelResponse)
def cancel_group_chat(
    group_id: Annotated[str, ApiPath(min_length=1, max_length=80)],
    service: GroupChatServiceDep,
) -> GroupCancelResponse:
    return service.cancel(group_id)
