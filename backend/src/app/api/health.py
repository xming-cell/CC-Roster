from fastapi import APIRouter
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health() -> HealthResponse:
    return HealthResponse(status="ok")
