"""022 托盘 / 快捷键 / 自启的后端边界。"""

from pathlib import Path

import pytest

from app.core.autostart import (
    AutostartError,
    AutostartManager,
    FileAutostartBackend,
    build_autostart_manager,
)
from app.core.errors import AppError
from app.core.hotkeys import (
    HotkeyConflict,
    HotkeyError,
    HotkeyManager,
    InMemoryHotkeyBackend,
    desktop_capabilities,
    normalize_hotkey,
)
from app.repositories.settings import SettingsRepository
from app.schemas.settings import SettingsUpdate
from app.services.settings_service import SettingsService


class FakeAutostart:
    def __init__(self) -> None:
        self.enabled = False
        self.calls: list[bool] = []
        self.fail = False

    def is_enabled(self) -> bool:
        return self.enabled

    def enable(self, command: str) -> None:
        if self.fail:
            raise AutostartError("denied")
        self.calls.append(True)
        self.enabled = True

    def disable(self) -> None:
        if self.fail:
            raise AutostartError("denied")
        self.calls.append(False)
        self.enabled = False


def test_hotkey_validation_default_and_duplicate_conflict() -> None:
    backend = InMemoryHotkeyBackend(occupied={"ctrl+alt+x"})
    manager = HotkeyManager(backend)

    assert normalize_hotkey("Ctrl + Alt + C") == "ctrl+alt+c"
    manager.set("ctrl+alt+c")
    assert manager.current == "ctrl+alt+c"
    with pytest.raises(HotkeyConflict):
        manager.set("ctrl+alt+x")
    assert manager.current == "ctrl+alt+c"
    with pytest.raises(HotkeyError):
        normalize_hotkey("c")
    with pytest.raises(HotkeyError):
        normalize_hotkey("ctrl+alt")
    manager.clear()
    assert manager.current is None


def test_file_autostart_writes_and_removes_linux_desktop_entry(tmp_path: Path) -> None:
    backend = FileAutostartBackend(tmp_path / "autostart" / "cc-roster.desktop", platform="linux")
    manager = AutostartManager(backend, command='"/usr/bin/python" -m app.desktop')

    manager.set_enabled(True)
    assert backend.is_enabled()
    text = backend.path.read_text(encoding="utf-8")
    assert "Name=CC-Roster" in text
    assert "Exec=" in text

    manager.set_enabled(False)
    assert not backend.is_enabled()


def test_macos_autostart_plist_contains_program_arguments(tmp_path: Path) -> None:
    backend = FileAutostartBackend(
        tmp_path / "LaunchAgents" / "com.ccroster.app.plist",
        platform="darwin",
    )
    manager = AutostartManager(backend, command='"/usr/bin/python3" -m app.desktop')

    manager.set_enabled(True)

    assert backend.path.exists()
    assert b"com.ccroster.app" in backend.path.read_bytes()
    assert b"app.desktop" in backend.path.read_bytes()


def test_autostart_manager_and_capabilities_degrade_cleanly(tmp_path: Path, monkeypatch) -> None:
    manager = build_autostart_manager(platform="linux", home=tmp_path, environ={})
    assert manager.is_enabled() is False

    with pytest.raises(AutostartError):
        build_autostart_manager(platform="unknown", home=tmp_path, environ={})

    tray, hotkey, autostart = desktop_capabilities()
    assert isinstance(tray, bool)
    assert isinstance(hotkey, bool)
    assert isinstance(autostart, bool)


def test_settings_service_persists_hotkey_and_autostart(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path)
    fake = FakeAutostart()
    service = SettingsService(repository, autostart=AutostartManager(fake))

    updated = service.update(SettingsUpdate(hotkey="Ctrl+Shift+K", autostart=True))

    assert updated.hotkey == "ctrl+shift+k"
    assert updated.autostart is True
    assert fake.enabled is True
    assert repository.load().autostart is True

    service.update(SettingsUpdate(autostart=False))
    assert fake.enabled is False


def test_invalid_hotkey_and_failed_autostart_do_not_persist(tmp_path: Path) -> None:
    repository = SettingsRepository(tmp_path)
    fake = FakeAutostart()
    service = SettingsService(repository, autostart=AutostartManager(fake))

    with pytest.raises(AppError) as invalid:
        service.update(SettingsUpdate(hotkey="not-a-hotkey"))
    assert invalid.value.code == "HOTKEY_INVALID"

    fake.fail = True
    with pytest.raises(AppError) as failed:
        service.update(SettingsUpdate(autostart=True))
    assert failed.value.code == "AUTOSTART_FAILED"
    assert repository.load().autostart is False
