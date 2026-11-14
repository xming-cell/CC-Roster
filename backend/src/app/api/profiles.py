"""档案 CRUD API。

端点只做参数绑定与转发, 业务规则全部在 `ProfileService`;
错误统一抛 `AppError`, 由全局异常处理器转成 `{code, message}`。
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from app.adapters.registry import build_registry
from app.core.config import settings
from app.core.paths import resolve_data_dir
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import build_secret_store
from app.schemas.health_check import HealthCheckRequest, HealthCheckResponse
from app.schemas.profile import (
    BindingDeleteResponse,
    BindingView,
    BindProfileRequest,
    ProfileCopyRequest,
    ProfileCreate,
    ProfileDeleteResponse,
    ProfileListResponse,
    ProfileUpdate,
    ProfileView,
)
from app.services.health_check import HealthCheckService, UrllibHealthCheckTransport
from app.services.profile_service import ProfileService
from app.services.tool_discovery import ToolDiscoveryService

router = APIRouter(tags=["profiles"])


def get_profile_service() -> ProfileService:
    """每个请求按当前数据目录与环境构造服务, 不做进程内缓存。"""
    data_dir = Path(resolve_data_dir())
    return ProfileService(
        ProfileRepository(data_dir),
        build_secret_store(data_dir, mode=settings.secret_backend),
        ToolDiscoveryService(build_registry()),
    )


def get_health_check_service() -> HealthCheckService:
    data_dir = Path(resolve_data_dir())
    return HealthCheckService(
        ProfileRepository(data_dir),
        build_secret_store(data_dir, mode=settings.secret_backend),
        UrllibHealthCheckTransport(),
    )


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]
HealthCheckServiceDep = Annotated[HealthCheckService, Depends(get_health_check_service)]


@router.get("/api/profiles", response_model=ProfileListResponse)
def list_profiles(service: ProfileServiceDep) -> ProfileListResponse:
    return service.list_profiles()


@router.post("/api/profiles", response_model=ProfileView, status_code=201)
def create_profile(payload: ProfileCreate, service: ProfileServiceDep) -> ProfileView:
    return service.create_profile(payload)


@router.get("/api/profiles/{profile_id}", response_model=ProfileView)
def get_profile(profile_id: str, service: ProfileServiceDep) -> ProfileView:
    return service.get_profile(profile_id)


@router.patch("/api/profiles/{profile_id}", response_model=ProfileView)
def update_profile(
    profile_id: str,
    payload: ProfileUpdate,
    service: ProfileServiceDep,
) -> ProfileView:
    return service.update_profile(profile_id, payload)


@router.post("/api/profiles/{profile_id}/copy", response_model=ProfileView, status_code=201)
def copy_profile(
    profile_id: str,
    service: ProfileServiceDep,
    payload: ProfileCopyRequest | None = None,
) -> ProfileView:
    return service.copy_profile(profile_id, payload)


@router.delete("/api/profiles/{profile_id}", response_model=ProfileDeleteResponse)
def delete_profile(
    profile_id: str,
    service: ProfileServiceDep,
    confirm: bool = False,
) -> ProfileDeleteResponse:
    return service.delete_profile(profile_id, confirm=confirm)


@router.put("/api/tools/{tool_id}/profile", response_model=BindingView)
def bind_tool_profile(
    tool_id: str,
    payload: BindProfileRequest,
    service: ProfileServiceDep,
) -> BindingView:
    return service.bind_tool(tool_id, payload.profile_id)


@router.delete("/api/tools/{tool_id}/profile", response_model=BindingDeleteResponse)
def unbind_tool_profile(
    tool_id: str,
    service: ProfileServiceDep,
) -> BindingDeleteResponse:
    return service.unbind_tool(tool_id)


@router.post(
    "/api/profiles/{profile_id}/health-check",
    response_model=HealthCheckResponse,
)
def health_check_profile(
    profile_id: str,
    service: HealthCheckServiceDep,
    payload: HealthCheckRequest | None = None,
) -> HealthCheckResponse:
    return service.check(profile_id, payload or HealthCheckRequest())
