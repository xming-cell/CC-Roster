"""原生目录选择: 命令构造、取消、降级与超时。"""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.services.directory_picker import DirectoryPickerService


class FakeRunner:
    def __init__(self, completed: subprocess.CompletedProcess[str] | Exception) -> None:
        self.completed = completed
        self.calls: list[list[str]] = []

    def __call__(
        self, command: Sequence[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(command))
        if isinstance(self.completed, Exception):
            raise self.completed
        return self.completed


def which_factory(mapping: dict[str, str | None]):
    def which(name: str) -> str | None:
        return mapping.get(name)

    return which


def test_windows_uses_sta_folder_dialog_and_returns_selected_path() -> None:
    runner = FakeRunner(
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=r'{"path":"D:\\projects\\demo","cancelled":false}',
            stderr="",
        )
    )
    service = DirectoryPickerService(
        platform="win32",
        which=which_factory(
            {"powershell.exe": "C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe"}
        ),
        runner=runner,
    )

    result = service.pick()

    assert result.cancelled is False
    assert result.path == str(Path("D:/projects/demo").resolve())
    assert any(part == "-STA" for part in runner.calls[0])
    assert "FolderBrowserDialog" in " ".join(runner.calls[0])


def test_windows_cancel_returns_cancelled_without_error() -> None:
    runner = FakeRunner(
        subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"path":null,"cancelled":true}',
            stderr="",
        )
    )
    service = DirectoryPickerService(
        platform="win32",
        which=which_factory({"powershell.exe": "powershell.exe"}),
        runner=runner,
    )

    result = service.pick()

    assert result.cancelled is True
    assert result.path is None


def test_macos_osascript_returns_path_and_treats_exit_one_as_cancel() -> None:
    runner = FakeRunner(
        subprocess.CompletedProcess(args=[], returncode=0, stdout="/Users/me/demo\n", stderr="")
    )
    service = DirectoryPickerService(
        platform="darwin",
        which=which_factory({"osascript": "/usr/bin/osascript"}),
        runner=runner,
    )
    assert service.pick().path == "/Users/me/demo"
    assert "choose folder" in " ".join(runner.calls[0])

    runner.completed = subprocess.CompletedProcess(
        args=[], returncode=1, stdout="", stderr="User canceled"
    )
    assert service.pick().cancelled is True


def test_linux_prefers_zenity_then_kdialog() -> None:
    runner = FakeRunner(
        subprocess.CompletedProcess(args=[], returncode=0, stdout="/home/me/demo\n", stderr="")
    )
    service = DirectoryPickerService(
        platform="linux",
        which=which_factory({"zenity": "/usr/bin/zenity", "kdialog": "/usr/bin/kdialog"}),
        runner=runner,
    )
    assert service.pick().path == "/home/me/demo"
    assert "zenity" in runner.calls[0][0]

    runner.completed = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
    assert service.pick().cancelled is True


def test_unavailable_backend_returns_501() -> None:
    service = DirectoryPickerService(
        platform="linux",
        which=which_factory({"zenity": None, "kdialog": None}),
        runner=FakeRunner(subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")),
    )

    with pytest.raises(AppError) as exc:
        service.pick()
    assert exc.value.status_code == 501
    assert exc.value.code == "DIRECTORY_PICKER_UNAVAILABLE"


def test_timeout_and_invalid_output_are_readable_errors() -> None:
    timeout_service = DirectoryPickerService(
        platform="linux",
        which=which_factory({"zenity": "/usr/bin/zenity"}),
        runner=FakeRunner(subprocess.TimeoutExpired(cmd=["zenity"], timeout=1)),
    )
    with pytest.raises(AppError) as timeout_exc:
        timeout_service.pick()
    assert timeout_exc.value.status_code == 504

    invalid_service = DirectoryPickerService(
        platform="win32",
        which=which_factory({"powershell.exe": "powershell.exe"}),
        runner=FakeRunner(
            subprocess.CompletedProcess(args=[], returncode=0, stdout="not-json", stderr="")
        ),
    )
    with pytest.raises(AppError) as invalid_exc:
        invalid_service.pick()
    assert invalid_exc.value.status_code == 502
