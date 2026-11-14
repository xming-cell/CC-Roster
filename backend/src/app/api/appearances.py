"""好友外观覆盖 API。"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi import Path as ApiPath

from app.core.paths import resolve_data_dir
from app.repositories.appearances import AppearanceRepository
from app.schemas.appearance import (
    AppearanceListResponse,
    AppearanceOverride,
    AppearanceResetResponse,
    AppearanceView,
)
from app.services.appearance_service import AppearanceService

router = APIRouter(tags=["appearances"])


def get_appearance_service() -> AppearanceService:
    return AppearanceService(AppearanceRepository(Path(resolve_data_dir())))


AppearanceServiceDep = Annotated[AppearanceService, Depends(get_appearance_service)]
ToolId = Annotated[str, ApiPath(min_length=1, max_length=120)]


@router.get("/api/appearances", response_model=AppearanceListResponse)
def list_appearances(service: AppearanceServiceDep) -> AppearanceListResponse:
    return service.list_appearances()


@router.put("/api/appearances/{tool_id}", response_model=AppearanceView)
def save_appearance(
    tool_id: ToolId,
    payload: AppearanceOverride,
    service: AppearanceServiceDep,
) -> AppearanceView:
    return service.save_appearance(tool_id, payload)


@router.delete("/api/appearances/{tool_id}", response_model=AppearanceResetResponse)
def reset_appearance(tool_id: ToolId, service: AppearanceServiceDep) -> AppearanceResetResponse:
    return service.reset_appearance(tool_id)
