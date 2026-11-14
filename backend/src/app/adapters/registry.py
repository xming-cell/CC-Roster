"""显式适配器注册表。

v1 只支持代码内的显式清单, 不从任意路径动态加载插件 (ADR 附录 A.4)。
单个适配器初始化失败只产生 `ADAPTER_ERROR` warning, 不影响其他工具;
未知工具 ID 在 `get()` 处按 `TOOL_NOT_FOUND` 处理。
"""

import os
import shutil
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

from app.adapters.base import ToolAdapter, ToolWarning
from app.adapters.claude_code import ClaudeCodeAdapter, resolve_claude_config_dir
from app.adapters.codex_cli import CodexCliAdapter, resolve_codex_config_dir
from app.adapters.gemini_cli import GeminiCliAdapter, resolve_gemini_config_dir
from app.adapters.opencode import OpenCodeAdapter, resolve_opencode_config_dir
from app.core.errors import AppError

WhichFn = Callable[[str], str | None]
Environ = Mapping[str, str]


@dataclass(frozen=True, slots=True)
class AdapterContext:
    """适配器可注入的外部环境; 测试不依赖真实 PATH / home / 进程环境。"""

    environ: Environ
    home: Path
    which: WhichFn


def default_context(
    *,
    environ: Environ | None = None,
    home: Path | None = None,
    which: WhichFn | None = None,
) -> AdapterContext:
    """按进程环境构造上下文; 三个参数都可显式注入。"""
    return AdapterContext(
        environ=os.environ if environ is None else environ,
        home=Path.home() if home is None else home,
        which=shutil.which if which is None else which,
    )


@dataclass(frozen=True, slots=True)
class AdapterRegistration:
    """显式注册项; `tool_id` 用于隔离失败并校验适配器自报的 id。"""

    tool_id: str
    factory: Callable[[AdapterContext], ToolAdapter]


def _build_claude_code(context: AdapterContext) -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter(
        resolve_claude_config_dir(environ=context.environ, home=context.home),
        which=context.which,
    )


def _build_codex_cli(context: AdapterContext) -> CodexCliAdapter:
    return CodexCliAdapter(
        resolve_codex_config_dir(environ=context.environ, home=context.home),
        which=context.which,
    )


def _build_gemini_cli(context: AdapterContext) -> GeminiCliAdapter:
    return GeminiCliAdapter(
        resolve_gemini_config_dir(environ=context.environ, home=context.home),
        which=context.which,
        environ=context.environ,
    )


def _build_opencode(context: AdapterContext) -> OpenCodeAdapter:
    return OpenCodeAdapter(
        resolve_opencode_config_dir(environ=context.environ, home=context.home),
        which=context.which,
        environ=context.environ,
    )


# 显式清单: 新增适配器在这里追加, 不做动态发现。
_ADAPTER_REGISTRATIONS: tuple[AdapterRegistration, ...] = (
    AdapterRegistration("claude-code", _build_claude_code),
    AdapterRegistration("codex-cli", _build_codex_cli),
    AdapterRegistration("gemini-cli", _build_gemini_cli),
    AdapterRegistration("opencode", _build_opencode),
)


class ToolRegistry:
    """按适配器 id 索引的只读注册表; 重复 id 只保留第一个并记 warning。"""

    def __init__(
        self,
        adapters: Iterable[ToolAdapter],
        warnings: Iterable[ToolWarning] = (),
    ) -> None:
        self._adapters: dict[str, ToolAdapter] = {}
        self._warnings = list(warnings)
        for adapter in adapters:
            if adapter.id in self._adapters:
                self._warnings.append(
                    ToolWarning(
                        code="ADAPTER_ERROR",
                        message=f"适配器 id 重复, 已忽略: {adapter.id}",
                    )
                )
                continue
            self._adapters[adapter.id] = adapter

    @property
    def adapters(self) -> tuple[ToolAdapter, ...]:
        """按注册顺序返回适配器。"""
        return tuple(self._adapters.values())

    @property
    def warnings(self) -> tuple[ToolWarning, ...]:
        """构造期降级原因; 运行期解析 warnings 由各适配器 / 服务负责。"""
        return tuple(self._warnings)

    def get(self, tool_id: str) -> ToolAdapter:
        adapter = self._adapters.get(tool_id)
        if adapter is None:
            raise AppError("TOOL_NOT_FOUND", f"未知工具: {tool_id}", status_code=404)
        return adapter


def build_registry(
    *,
    context: AdapterContext | None = None,
    registrations: Iterable[AdapterRegistration] | None = None,
) -> ToolRegistry:
    """按显式清单构造注册表; 工厂异常与 id 不匹配都降级为 warning。"""
    ctx = default_context() if context is None else context
    entries = _ADAPTER_REGISTRATIONS if registrations is None else tuple(registrations)

    adapters: list[ToolAdapter] = []
    warnings: list[ToolWarning] = []
    for entry in entries:
        try:
            adapter = entry.factory(ctx)
        except Exception as exc:  # 隔离未知适配器异常是契约要求
            warnings.append(
                ToolWarning(
                    code="ADAPTER_ERROR",
                    message=f"适配器 {entry.tool_id} 初始化失败: {type(exc).__name__}",
                )
            )
            continue
        if adapter.id != entry.tool_id:
            warnings.append(
                ToolWarning(
                    code="ADAPTER_ERROR",
                    message=f"适配器 {entry.tool_id} 返回了不匹配的 id: {adapter.id}",
                )
            )
            continue
        adapters.append(adapter)

    return ToolRegistry(adapters, warnings)
