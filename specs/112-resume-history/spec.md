# 038 — 从历史会话继续

> 来源：用户 2026-11-17 追加需求（对应规划 112）；修订 107 的只读边界（新建 ADR-017）。
> 依赖：107（历史回放）已完成；本机已核实 Claude `--resume` 与 Codex `exec resume`。

## 背景与目标

1. 现在历史只能只读回放，用户希望能接着上次对话继续问。
2. 目标：历史时间线提供「继续这段对话」，显式创建一个新的应用会话并从原会话恢复上下文。
3. 目标：只有声明支持 resume 的工具显示按钮；不支持的明确说明。
4. 目标：原历史仍然只读；继续动作写入的是新的应用会话，不改写我们读到的历史文件。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- `ToolCapabilities` 增加 `resume` / `resume_levels`（或等价字段）：Claude / Codex 为 true，其它为 false。
- Claude 命令追加 `--resume <session-id>`；Codex 使用 `exec resume <session-id>`（均已本机核实）。
- `ChatSession` 记录 `resume_from_tool_id` / `resume_from_session_id`；续聊命令携带恢复参数。
- 历史时间线显示「继续这段对话」；点击后创建新应用会话并切到对话视图，首条消息沿用原模型 / 强度默认值。
- 不支持的工具隐藏按钮并说明原因；原会话文件不被本应用修改。
- 测试：能力表、命令映射、按钮可见性、创建会话字段、发送时命令带 resume。
- 设计稿（历史时间线加按钮 + 续聊成功提示）经用户确认。

## 范围

```scope
backend/src/**
backend/tests/**
frontend/src/**
docs/design/**
docs/task-board.md
```

## 边界用例（实现时必须想到）

1. 会话 id 含特殊字符 → 只作为参数传递，不拼 shell 字符串。
2. 原会话已被删除 / 工具版本不支持 resume → 可读错误，不产生半截会话。
3. 同一历史重复点「继续」→ 复用或新建的策略要确定（建议每次新建，标题加「续」）。
4. 续聊期间历史视图不自动刷新，避免阅读位置跳动。
5. 继续动作不得把原工具会话文件写坏；如需工具自身追加，在文档中说明这是工具行为。

## 不做（明确划界）

- 不做「分叉 / fork」语义的 UI（Codex 支持 fork，但本期只做 resume）。
- 不做跨工具续聊（Claude 会话不能用 Codex 恢复）。
- 不改历史回放的只读默认与 hash 校验。
