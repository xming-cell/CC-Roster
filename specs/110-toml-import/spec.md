# 036 — TOML 导入与 Codex 配置读取

> 来源：用户 2026-11-17 追加需求（对应规划 110）；修订 ADR-012。
> 依赖：105（JSON 导入）已完成。

## 背景与目标

1. 本机 Codex CLI 的配置是 TOML（`~/.codex/config.toml`），现有导入只接受 JSON，用户需要手工转换。
2. 目标 1：导入接受版本化 TOML（`schema_version = 1` + `[[profiles]]`），保留 JSON v1 兼容。
3. 目标 2：新增「从 Codex 配置导入」，直接读取 `CODEX_HOME` 或 `~/.codex/config.toml` 并预览。
4. 目标 3：配置里的 bearer token / env key 只进本机密钥库，预览、审计、日志都不回显。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- `.toml` 导入与 JSON 导入共用同一套校验、去重（名称+协议+地址）、skip/overwrite 与全或无。
- 从 Codex 配置读取时：`model` 映射默认模型，`model_providers.<id>` 逐条生成候选；`wire_api` 只接受 responses / chat（映射 openai），其它标非法。
- `experimental_bearer_token`、`env_key` 等字段按密钥处理：预览只显示「有密钥 / 无密钥」；导入后写入密钥存储；审计无明文。
- 文件不存在 / 不可读 / TOML 解析失败 / 未知 `schema_version` / 空 profiles 都有可读错误。
- 不导入 `mcp_servers`、`plugins`、`projects` 等非供应商配置。
- 导入对话框新增「从 Codex 配置读取」入口，设计稿经用户确认。
- 测试覆盖 TOML 合法 / 非法 / 重复 / 超长 / 未知版本 / 直接读取 Codex 配置。

## 范围

```scope
backend/src/**
backend/tests/**
frontend/src/**
docs/design/**
docs/task-board.md
```

## 边界用例（实现时必须想到）

1. `model_providers` 有多个 provider → 每个一条候选；名称冲突时加 provider id 后缀。
2. 只有 `env_key` 没有明文 token → 允许导入，标 `has_secret=false` 并提示。
3. TOML 里 token 是明文 → 立即转存密钥库，原文件不改。
4. `base_url` 非法 / 缺 `wire_api` / 未知协议 → 该条 invalid，整批不写。
5. 文件里有 CRLF / BOM / 注释 → 正常解析。

## 不做（明确划界）

- 不把本应用的内部存储（`profiles.json`）改成 TOML；只改导入格式与外部配置读取。
- 不反向写回 `~/.codex/config.toml`。
- 不导入 Claude / Gemini / OpenCode 的配置（后续按需）。
- 不在日志或错误信息里输出 token 明文。
