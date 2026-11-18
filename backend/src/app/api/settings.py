"""运行期设置 API: 只读开关。"""

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.autostart import AutostartError, build_autostart_manager
from app.core.paths import resolve_data_dir
from app.repositories.settings import SettingsRepository
from app.schemas.settings import SettingsUpdate, SettingsView
from app.services.settings_service import SettingsService

router = APIRouter(tags=["settings"])


def get_settings_service() -> SettingsService:
    try:
        autostart = build_autostart_manager()
    except AutostartError:
        autostart = None
    return SettingsService(
        SettingsRepository(Path(resolve_data_dir())),
        autostart=autostart,
    )


SettingsServiceDep = Annotated[SettingsService, Depends(get_settings_service)]


@router.get("/api/settings", response_model=SettingsView)
def get_settings(service: SettingsServiceDep) -> SettingsView:
    return service.get()


@router.put("/api/settings", response_model=SettingsView)
def update_settings(payload: SettingsUpdate, service: SettingsServiceDep) -> SettingsView:
    return service.update(payload)
