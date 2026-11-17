"""档案 CRUD API。

端点只做参数绑定与转发, 业务规则全部在 `ProfileService`;
错误统一抛 `AppError`, 由全局异常处理器转成 `{code, message}`。
"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.adapters.registry import build_registry
from app.core.config import settings
from app.core.errors import AppError
from app.core.paths import resolve_data_dir
from app.repositories.audit import AuditRepository
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
from app.schemas.profile_import import (
    ProfileImportPreview,
    ProfileImportRequest,
    ProfileImportResult,
)
from app.services.health_check import HealthCheckService, UrllibHealthCheckTransport
from app.services.profile_import_service import ProfileImportService
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
        AuditRepository(data_dir / "db" / "app.sqlite3"),
    )


def get_health_check_service() -> HealthCheckService:
    data_dir = Path(resolve_data_dir())
    return HealthCheckService(
        ProfileRepository(data_dir),
        build_secret_store(data_dir, mode=settings.secret_backend),
        UrllibHealthCheckTransport(),
    )


ProfileServiceDep = Annotated[ProfileService, Depends(get_profile_service)]


def get_profile_import_service() -> ProfileImportService:
    """导入按当前数据目录与环境构造, 与 CRUD 服务共享同一份存储。"""
    data_dir = Path(resolve_data_dir())
    return ProfileImportService(
        ProfileRepository(data_dir),
        build_secret_store(data_dir, mode=settings.secret_backend),
        AuditRepository(data_dir / "db" / "app.sqlite3"),
    )


ProfileImportServiceDep = Annotated[ProfileImportService, Depends(get_profile_import_service)]
HealthCheckServiceDep = Annotated[HealthCheckService, Depends(get_health_check_service)]


@router.get("/api/profiles", response_model=ProfileListResponse)
def list_profiles(
    service: ProfileServiceDep,
    tool_id: Annotated[str | None, Query()] = None,
) -> ProfileListResponse:
    return service.list_profiles(tool_id=_normalize_optional_id(tool_id, "tool_id"))


@router.post("/api/profiles", response_model=ProfileView, status_code=201)
def create_profile(payload: ProfileCreate, service: ProfileServiceDep) -> ProfileView:
    return service.create_profile(payload)


@router.post("/api/profiles/import/preview", response_model=ProfileImportPreview)
def preview_profile_import(
    payload: ProfileImportRequest,
    service: ProfileImportServiceDep,
) -> ProfileImportPreview:
    return service.preview(payload)


@router.post("/api/profiles/import", response_model=ProfileImportResult, status_code=201)
def import_profiles(
    payload: ProfileImportRequest,
    service: ProfileImportServiceDep,
) -> ProfileImportResult:
    return service.import_profiles(payload)


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
    profile_id: Annotated[str, Query()],
) -> BindingDeleteResponse:
    """兼容入口; 必须指定 `profile_id`, 不会清空该工具的全部绑定。"""
    return service.unbind_tool(tool_id, _normalize_required_id(profile_id, "profile_id"))


@router.delete(
    "/api/tools/{tool_id}/profiles/{profile_id}",
    response_model=BindingDeleteResponse,
)
def unbind_tool_profile_by_id(
    tool_id: str,
    profile_id: str,
    service: ProfileServiceDep,
) -> BindingDeleteResponse:
    return service.unbind_tool(tool_id, _normalize_required_id(profile_id, "profile_id"))


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


def _normalize_required_id(value: str, field: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise AppError("VALIDATION_ERROR", f"{field} 不能为空", 422)
    return normalized


def _normalize_optional_id(value: str | None, field: str) -> str | None:
    if value is None:
        return None
    return _normalize_required_id(value, field)
