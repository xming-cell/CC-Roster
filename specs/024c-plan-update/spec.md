# 024c — 2026-11-17 追加需求登记

> 性质：规划收口卡，不写业务代码。

## 背景与目标

1. 用户提出 4 项追加需求：导入改 TOML、直接读取 `~/.codex/config.toml`、原生目录选择器、历史会话可继续。
2. 108/109 未覆盖这些点，需要建卡、写 ADR、更新总表与计划，避免丢失。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- `docs/decisions.md` 新增 ADR-015～017。
- `specs/110-toml-import`、`specs/111-directory-picker`、`specs/112-resume-history` 建卡并含 DoD / scope / 边界 / 不做。
- `docs/task-board.md` 与 `docs/task-plan2.md` 登记 110–112 及顺序（108 之后、109 之前）。
- 105/106/107 各加一行「后续修订」说明。

## 范围

```scope
docs/**
```

## 边界用例（实现时必须想到）

1. 解释「配置文件格式改 TOML」时明确：只改导入格式与外部配置读取，内部 `profiles.json` 不变。
2. 本机 config.toml 含明文 bearer token，文档不得写入具体值。
3. 新卡必须排在 109 之前，否则发布基线漏项。

## 不做（明确划界）

- 不实现 110–112 的任何代码。
- 不改 104–107 已完成的行为。
