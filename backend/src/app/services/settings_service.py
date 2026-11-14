"""只读开关用例。"""

from app.core.autostart import AutostartError, AutostartManager
from app.core.clock import utc_now
from app.core.errors import AppError
from app.core.hotkeys import HotkeyError, desktop_capabilities, normalize_hotkey
from app.repositories.settings import SettingsRepository
from app.schemas.settings import DesktopCapabilities, RuntimeSettings, SettingsUpdate, SettingsView


class SettingsService:
    def __init__(
        self,
        repository: SettingsRepository,
        *,
        autostart: AutostartManager | None = None,
    ) -> None:
        self._repository = repository
        self._autostart = autostart

    def get(self) -> SettingsView:
        settings = self._repository.load()
        tray, hotkey, autostart = desktop_capabilities()
        message = "只读模式已开启: 所有配置写入都会被拒绝" if settings.read_only else "可写模式"
        return SettingsView(
            read_only=settings.read_only,
            hotkey=settings.hotkey,
            autostart=settings.autostart,
            updated_at=settings.updated_at,
            message=message,
            capabilities=DesktopCapabilities(
                tray=tray,
                hotkey=hotkey,
                autostart=autostart,
            ),
        )

    def update(self, payload: SettingsUpdate) -> SettingsView:
        hotkey = None
        if payload.hotkey is not None:
            try:
                hotkey = normalize_hotkey(payload.hotkey)
            except HotkeyError as exc:
                raise AppError("HOTKEY_INVALID", str(exc), 400) from exc
        if payload.autostart is not None:
            if self._autostart is None:
                raise AppError(
                    "AUTOSTART_UNAVAILABLE",
                    "当前平台不支持开机自启",
                    400,
                )
            try:
                self._autostart.set_enabled(payload.autostart)
            except AutostartError as exc:
                raise AppError("AUTOSTART_FAILED", str(exc), 500) from exc

        def change(settings: RuntimeSettings) -> None:
            if payload.read_only is not None:
                settings.read_only = payload.read_only
            if hotkey is not None:
                settings.hotkey = hotkey
            if payload.autostart is not None:
                settings.autostart = payload.autostart
            settings.updated_at = utc_now()

        self._repository.mutate(change)
        return self.get()
