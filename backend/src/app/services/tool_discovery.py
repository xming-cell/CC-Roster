"""工具发现服务: 聚合适配器结果, 把单工具失败隔离成 warning。

适配器自己负责把可预期失败 (损坏 / 无权限 / 未知格式 / 版本不支持) 归一成
`ToolWarning`; 本层只兜住适配器的未知异常, 保证一个工具失败不影响其他工具。
列表与详情都直接读取文件, 不做缓存, 也不启动子进程。
"""

from collections.abc import Iterable

from app.adapters.base import (
    ERROR_WARNING_CODES,
    ToolAdapter,
    ToolWarning,
)
from app.adapters.registry import ToolRegistry
from app.core.errors import AppError
from app.schemas.tool import ToolListResponse, ToolStatus, ToolView


class ToolDiscoveryService:
    """只读工具发现; 构造时注入显式注册表, 便于测试替换适配器。"""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def list_tools(self) -> ToolListResponse:
        """未安装的工具不出现; 单个适配器异常降级为顶层 ADAPTER_ERROR。"""
        tools: list[ToolView] = []
        warnings = list(self._registry.warnings)
        for adapter in self._registry.adapters:
            try:
                view = self._discover(adapter)
            except Exception as exc:  # 隔离未知适配器异常是契约要求
                warnings.append(_adapter_error(adapter.id, exc))
                continue
            if view is not None:
                tools.append(view)
        return ToolListResponse(tools=tools, warnings=warnings)

    def get_tool(self, tool_id: str) -> ToolView:
        """按 id 读取单个工具; 未知 / 未安装 / 适配器异常都不返回 traceback。"""
        adapter = self._registry.get(tool_id)
        try:
            view = self._discover(adapter)
        except Exception as exc:  # 隔离未知适配器异常是契约要求
            raise AppError("ADAPTER_ERROR", _adapter_error(tool_id, exc).message, 500) from exc
        if view is None:
            raise AppError("TOOL_NOT_FOUND", f"工具未安装: {tool_id}", 404)
        return view

    @staticmethod
    def _discover(adapter: ToolAdapter) -> ToolView | None:
        detection = adapter.detect()
        if not detection.installed:
            return None
        result = adapter.read()
        warnings = _merge_warnings(detection.warnings, result.warnings)
        return ToolView(
            id=adapter.id,
            display_name=adapter.display_name,
            status=_status(detection.configured, warnings),
            installed=True,
            configured=detection.configured,
            version=detection.version,
            provider=result.provider,
            base_url=result.base_url,
            model=result.model,
            is_third_party=result.is_third_party,
            config_path=detection.config_path,
            last_modified=detection.last_modified,
            has_secret=result.has_secret,
            secret_preview=result.secret_preview,
            warnings=warnings,
            capabilities=adapter.capabilities,
        )


def _status(configured: bool, warnings: Iterable[ToolWarning]) -> ToolStatus:
    """解析失败优先判 error; 否则按是否解析到托管字段区分 ok / unconfigured。"""
    if any(warning.code in ERROR_WARNING_CODES for warning in warnings):
        return "error"
    return "ok" if configured else "unconfigured"


def _merge_warnings(*groups: Iterable[ToolWarning]) -> list[ToolWarning]:
    """detect 与 read 会各自解析一遍, 相同 code + message 只保留一条。"""
    merged: list[ToolWarning] = []
    seen: set[tuple[str, str]] = set()
    for group in groups:
        for warning in group:
            key = (warning.code, warning.message)
            if key in seen:
                continue
            seen.add(key)
            merged.append(warning)
    return merged


def _adapter_error(tool_id: str, exc: Exception) -> ToolWarning:
    """只暴露异常类型: 异常文本可能带文件内容或密钥。"""
    return ToolWarning(
        code="ADAPTER_ERROR",
        message=f"适配器 {tool_id} 读取失败: {type(exc).__name__}",
    )
