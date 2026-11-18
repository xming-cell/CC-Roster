"""启动器 API: preview 零副作用, launch 才真正拉起终端。"""

import shutil
import sys
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends

from app.adapters.registry import build_registry
from app.core.config import settings
from app.core.paths import resolve_data_dir
from app.repositories.profiles import ProfileRepository
from app.repositories.secrets import build_secret_store
from app.schemas.launcher import LaunchPreview, LaunchRequest, LaunchResponse
from app.services.launcher import LaunchService, SubprocessTerminalSpawner

router = APIRouter(tags=["launcher"])


def get_launch_service() -> LaunchService:
    data_dir = Path(resolve_data_dir())
    return LaunchService(
        build_registry(),
        ProfileRepository(data_dir),
        build_secret_store(data_dir, mode=settings.secret_backend),
        which=shutil.which,
        spawner=SubprocessTerminalSpawner(),
        platform=sys.platform,
    )


LaunchServiceDep = Annotated[LaunchService, Depends(get_launch_service)]


@router.post("/api/launch/preview", response_model=LaunchPreview)
def preview_launch(payload: LaunchRequest, service: LaunchServiceDep) -> LaunchPreview:
    return service.preview(payload)


@router.post("/api/launch", response_model=LaunchResponse)
def launch(payload: LaunchRequest, service: LaunchServiceDep) -> LaunchResponse:
    return service.launch(payload)
