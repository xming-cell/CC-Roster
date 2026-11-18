# 037 — 原生项目目录选择

> 来源：用户 2026-11-17 追加需求（对应规划 111）；新建 ADR-016。
> 依赖：106（新建会话）已完成；当前是手动输入路径。

## 背景与目标

1. 浏览器 / Vue 页面拿不到系统绝对路径，手动输入目录容易出错。
2. 目标：点「浏览…」时由本机后端唤起系统文件夹选择器，返回绝对路径并回填。
3. 目标：平台不支持或用户取消时，回退到手动输入，不阻塞创建会话。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- 新增 `POST /api/system/pick-directory`：仅 loopback，返回 `{"path": "..."}`；用户取消返回 `cancelled=true`。
- Windows 用 FolderBrowserDialog（STA），macOS 用 osascript，Linux 用 zenity/kdialog；命令不可用时返回 501 与可读说明。
- 有超时（建议 120s）；超时 / 取消 / 失败都不抛 500 堆栈。
- 前端 `ProjectDirPrompt` 增加「浏览…」按钮；选择后回填输入框，仍需点「创建会话」确认。
- 选择器不读取目录内容，只返回路径；创建时仍走现有的目录存在 / 可读校验。
- 测试：平台命令构造、不可用降级、前端按钮交互；手动验收在 Windows 上真实弹窗一次。

## 范围

```scope
backend/src/**
backend/tests/**
frontend/src/**
docs/design/**
docs/task-board.md
```

## 边界用例（实现时必须想到）

1. 用户取消 → 前端保持原输入，不报错。
2. 非 Windows / 没有 zenity → 501，提示手动输入。
3. 同时点两次「浏览…」→ 第二次被忽略（防重复弹窗）。
4. 后端不是本机（远程部署）→ 不提供该能力，隐藏按钮。

## 不做（明确划界）

- 不引入 Electron / Tauri 桌面壳。
- 不做目录内容浏览、新建目录、最近目录列表。
- 不在没有用户点击时主动弹窗。
