# 023 — 跨平台 CI 对齐

## 背景与目标
- `codex/design-first` 保留前端回退状态，但应使用与 `codex/complete-task-plan` 相同的 CI 入口和平台矩阵。
- 让 Windows 专属 API 在 Linux / macOS 的静态类型检查中仍有显式、可靠的类型边界。

## 验收标准（DoD）
- `uv run python scripts/check.py` 退出码 0。
- CI 在 Ubuntu、macOS、Windows 上运行同一个 `scripts/check.py`。
- Windows 专属 API 不因运行平台的类型定义差异导致 mypy 失败。
- 前端仍保持 design-first 分支原有回退，不合入完整 UI。

## 范围

```scope
.github/workflows/ci.yml
backend/src/app/core/autostart.py
backend/src/app/services/launcher.py
```

## 边界用例（实现时必须想到）
1. 在 Linux 与 macOS 目标下，Windows 自启 / 控制台符号仍能静态检查。
2. Windows 平台仍使用注册表和新控制台原有行为。
3. CI 各平台使用同一验收入口，不因平台拆分而漏跑后端、前端检查。

## 不做（明确划界）
- 不把 `codex/complete-task-plan` 的前端实现覆盖到 design-first。
- 不修改测试断言来绕过工作流差异。
- 不新增依赖。
