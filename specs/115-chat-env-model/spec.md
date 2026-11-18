# 041 — 修复 Windows 聊天环境与 Claude 自定义模型

> 来源：用户 2026-11-18 真人对话验收反馈。
> 依赖：112（对话与历史续聊）已完成；109 验收中发现，回本卡修复。

## 背景与目标

1. 真实对话报错：`[claude-code:unrecognized_model] {"model":"deepseek-v4.1-flash-1017"}`。
2. 同一条错误还带：`The %SystemRoot% environment variable is not set. Bun needs this set in order for network requests to work.`
3. 根因 1：`LaunchService.environment()` 与子进程执行器只把 3 个工具变量传给子进程，替换掉了父进程环境；Windows 下 `SystemRoot` / `PATH` 等系统变量丢失。
4. 根因 2：Claude 已经把当前模型写入 `ANTHROPIC_MODEL`，命令构造又额外传 `--model <自定义模型>`；Claude Code 会先校验模型名并拒绝非 Anthropic 模型。
5. 目标：子进程继承父环境后再覆盖工具变量；Claude 只用 `ANTHROPIC_MODEL` 选择模型，不再传 `--model`；标准 Claude 模型与第三方 Anthropic 兼容模型都可对话。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- 聊天子进程环境保留父进程的 `SystemRoot`、`PATH` 等变量，同时正确覆盖 `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_MODEL`。
- 终端启动路径同样保留父环境，不再把环境替换成 3 个变量。
- Claude 命令不再出现 `--model`；当前会话模型通过 `ANTHROPIC_MODEL` 传递，模型切换后环境值随之更新。
- Codex 命令的 `--model` 行为保持不变。
- 测试覆盖：父环境保留、SystemRoot 存在、Claude 无 `--model`、Claude 会话模型进入 env、Codex 仍带 `--model`。
- 真实对话复测：DeepSeek / 第三方 Anthropic 兼容模型可正常返回，不再报 `unrecognized_model` 或 SystemRoot 缺失。

## 范围

```scope
backend/src/**
backend/tests/**
docs/task-board.md
```

## 边界用例（实现时必须想到）

1. Windows 父环境有 `SystemRoot`，子进程环境必须包含它。
2. `PATH` 不能被覆盖为空，Claude / Bun 仍能找到依赖。
3. 工具变量必须覆盖父环境中的同名旧值，避免串用旧供应商。
4. Claude 标准模型与自定义模型都只依赖 `ANTHROPIC_MODEL`；`--effort`、`--resume` 保留。
5. Codex 自定义模型仍通过 `--model` 传递。
6. 不在日志 / 错误响应中输出密钥或完整环境。

## 不做（明确划界）

- 不改前端模型选择 UI。
- 不新增模型能力校验表；先修正环境与 Claude 命令映射。
- 不修 109 验收文档以外的业务行为；本卡只处理上述两个根因。