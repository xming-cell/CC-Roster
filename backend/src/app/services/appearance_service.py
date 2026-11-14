"""好友外观覆盖的用例边界。"""

from app.core.errors import AppError
from app.repositories.appearances import AppearanceRepository
from app.schemas.appearance import (
    AppearanceListResponse,
    AppearanceOverride,
    AppearanceResetResponse,
    AppearanceView,
)

MAX_TOOL_ID_LENGTH = 120


class AppearanceService:
    def __init__(self, repository: AppearanceRepository) -> None:
        self._repository = repository

    def list_appearances(self) -> AppearanceListResponse:
        store = self._repository.list()
        return AppearanceListResponse(
            schema_version=store.schema_version,
            appearances=store.appearances,
        )

    def save_appearance(
        self,
        tool_id: str,
        appearance: AppearanceOverride,
    ) -> AppearanceView:
        normalized_id = self._validate_tool_id(tool_id)
        self._repository.save(normalized_id, appearance)
        return AppearanceView(tool_id=normalized_id, **appearance.model_dump())

    def reset_appearance(self, tool_id: str) -> AppearanceResetResponse:
        normalized_id = self._validate_tool_id(tool_id)
        self._repository.reset(normalized_id)
        return AppearanceResetResponse(tool_id=normalized_id)

    @staticmethod
    def _validate_tool_id(tool_id: str) -> str:
        normalized = tool_id.strip()
        if not normalized or len(normalized) > MAX_TOOL_ID_LENGTH:
            raise AppError("APPEARANCE_INVALID", "工具 ID 必须为 1 至 120 个字符", 422)
        return normalized
