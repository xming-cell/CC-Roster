"""目录选择端点: 成功、取消与不可用响应。"""

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.system import get_directory_picker_service
from app.core.errors import AppError
from app.main import create_app
from app.schemas.directory_picker import DirectoryPickResponse


class FakePicker:
    def __init__(self, response: DirectoryPickResponse | Exception) -> None:
        self.response = response

    def pick(self) -> DirectoryPickResponse:
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def client_for(picker: FakePicker) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_directory_picker_service] = lambda: picker
    return TestClient(app)


def test_pick_directory_returns_the_selected_path() -> None:
    selected = str(Path("/tmp/demo"))
    response = client_for(FakePicker(DirectoryPickResponse(path=selected))).post(
        "/api/system/pick-directory"
    )

    assert response.status_code == 200
    assert response.json() == {"path": selected, "cancelled": False}


def test_pick_directory_returns_cancelled_without_error() -> None:
    response = client_for(FakePicker(DirectoryPickResponse(cancelled=True))).post(
        "/api/system/pick-directory"
    )

    assert response.status_code == 200
    assert response.json() == {"path": None, "cancelled": True}


def test_pick_directory_maps_unavailable_backend_to_501() -> None:
    picker = FakePicker(AppError("DIRECTORY_PICKER_UNAVAILABLE", "当前平台不支持系统目录选择", 501))
    response = client_for(picker).post("/api/system/pick-directory")

    assert response.status_code == 501
    assert response.json()["code"] == "DIRECTORY_PICKER_UNAVAILABLE"
