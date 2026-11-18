"""会话回放用例: 跨工具聚合、分页、只读与单适配器故障隔离。"""

from __future__ import annotations

from app.adapters.base import ToolWarning
from app.adapters.registry import ToolRegistry
from app.core.errors import AppError
from app.schemas.session import SessionListResponse, SessionMessagesResponse, SessionSummary


class SessionService:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def list_sessions(
        self,
        *,
        tool_id: str | None,
        limit: int,
        cursor: int,
    ) -> SessionListResponse:
        adapters = (
            [self._registry.get(tool_id)] if tool_id is not None else list(self._registry.adapters)
        )
        summaries: list[SessionSummary] = []
        warnings: list[ToolWarning] = []
        for adapter in adapters:
            if not adapter.capabilities.sessions:
                continue
            try:
                found = adapter.list_sessions()
            except Exception as exc:
                warnings.append(
                    ToolWarning(
                        code="ADAPTER_ERROR",
                        message=f"{adapter.display_name} 会话列表读取失败: {type(exc).__name__}",
                    )
                )
                continue
            summaries.extend(found)
            for summary in found:
                warnings.extend(summary.warnings)

        summaries.sort(key=lambda item: item.updated_at, reverse=True)
        total = len(summaries)
        page = summaries[cursor : cursor + limit]
        next_cursor = cursor + limit if cursor + limit < total else None
        return SessionListResponse(
            sessions=page,
            warnings=warnings,
            next_cursor=next_cursor,
            has_more=next_cursor is not None,
        )

    def read_session(
        self,
        tool_id: str,
        session_id: str,
        *,
        limit: int,
        cursor: int,
    ) -> SessionMessagesResponse:
        adapter = self._registry.get(tool_id)
        if not adapter.capabilities.sessions:
            raise AppError("SESSION_UNSUPPORTED", f"{adapter.display_name} 不支持会话回放", 400)
        try:
            messages, has_more, warnings = adapter.read_session_messages(
                session_id,
                offset=cursor,
                limit=limit,
            )
        except FileNotFoundError as exc:
            raise AppError("SESSION_NOT_FOUND", "会话不存在或已被外部删除", 404) from exc
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "SESSION_UNREADABLE",
                f"会话读取失败: {type(exc).__name__}",
                500,
            ) from exc
        next_cursor = cursor + len(messages) if has_more else None
        return SessionMessagesResponse(
            tool_id=tool_id,
            session_id=session_id,
            messages=messages,
            next_cursor=next_cursor,
            has_more=has_more,
            warnings=warnings,
        )
