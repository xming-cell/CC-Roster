"""系统能力 API: 原生文件夹选择器。"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.directory_picker import DirectoryPickResponse
from app.services.directory_picker import DirectoryPickerService

router = APIRouter(tags=["system"])


def get_directory_picker_service() -> DirectoryPickerService:
    return DirectoryPickerService()


DirectoryPickerDep = Annotated[DirectoryPickerService, Depends(get_directory_picker_service)]


@router.post("/api/system/pick-directory", response_model=DirectoryPickResponse)
def pick_directory(service: DirectoryPickerDep) -> DirectoryPickResponse:
    return service.pick()
