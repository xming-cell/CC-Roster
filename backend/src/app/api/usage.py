"""用量汇总 API。"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.adapters.registry import build_registry
from app.schemas.usage import UsageResponse
from app.services.usage_service import UsageService

router = APIRouter(tags=["usage"])


def get_usage_service() -> UsageService:
    return UsageService(build_registry())


UsageServiceDep = Annotated[UsageService, Depends(get_usage_service)]


@router.get("/api/usage", response_model=UsageResponse)
def get_usage(
    service: UsageServiceDep,
    days: Annotated[int, Query(ge=1, le=365)] = 7,
) -> UsageResponse:
    return service.summarize(days)
