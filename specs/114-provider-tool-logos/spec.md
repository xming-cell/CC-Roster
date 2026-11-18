# 040 — 提供商页工具列表 logo 缺失

> 来源：用户 2026-11-18 反馈（对应规划 114）。
> 依赖：103（供应商页）已完成；101 的工具列表与 6cfc806 的官方 SVG logo 已完成。

## 背景与目标

1. 工具页的工具列表使用 `ToolLogo` 渲染 Claude / Codex / Gemini / OpenCode 的官方 SVG。
2. 提供商页左侧工具列表仍渲染一个通用方框图标，导致切换页面后看不到对应工具品牌 logo。
3. 目标：提供商页工具列表恢复与工具页一致的品牌 logo；未知工具继续走统一 fallback，不新增图片资源。

## 已定位原因

- `frontend/src/components/ProviderToolItem.vue` 的图标容器里直接写了通用 `<svg>`（方框 + 命令提示符），没有使用 `ToolLogo`。
- `frontend/src/components/ToolListItem.vue` 已正确使用 `<ToolLogo :tool-id="tool.id" size="sm" />`，可作为参考实现。
- `frontend/src/utils/toolLogos.ts` 已包含四个工具的官方 SVG 路径，不需要新增资源或改后端。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- 提供商页左侧工具列表对 Claude Code / Codex CLI / Gemini CLI / OpenCode 显示对应品牌 logo，尺寸与工具页一致（图标容器 24×24，logo 16×16）。
- 未知 `tool_id` 仍显示统一 fallback，不出现破图或空白。
- 选中 / hover 状态不改变官方 logo 自身的品牌颜色；容器背景与现有供应商页设计一致。
- 组件测试覆盖：已知工具渲染品牌 logo、未知工具渲染 fallback；不因修复破坏工具选择与供应商汇总文本。
- 不修改后端、不新增 logo 资源、不改 Penpot 设计；复用 103 已确认的工具列表 logo 规格。

## 范围

```scope
frontend/src/**
docs/task-board.md
```

## 边界用例（实现时必须想到）

1. `tool_id` 为未知值 → fallback 仍可见，不抛错。
2. 工具处于未配置 / 异常状态 → logo 正常显示，状态徽章与摘要不受影响。
3. 选中态容器背景变化 → logo 颜色保持官方值，不被 `currentColor` 覆盖。
4. 窄屏 / 列表重排 → logo 不拉伸、不溢出 24×24 容器。

## 不做（明确划界）

- 不新增或重画 logo 资源。
- 不改工具页、对话页已使用的 `ToolLogo`。
- 不为该缺陷新增 Penpot 画板；如用户要求视觉确认，再单独出局部对比图。