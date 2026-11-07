# 进度

## 当前状态

- 骨架完成：后端 health 端点 + 1 个测试；前端调通 `/api/health`；`scripts/check.py` 七道门 + CI 打通。
- 工作流基线加固完成（任务卡 001）：规则已机器化，`check.py` 现在含 `guard scope` / `guard forbidden` 两步硬门禁。
- 根目录 `README.md` 已改写为「产品介绍 + 开发者上手」文档；该文件已在 001 卡 scope 中登记（同卡文档改动）。
- 最近一次验收：见 `specs/001-ai-collab-baseline/tasks.md` 的「验收记录」。

## 下一个可执行命令

```bash
# 1) 任何时候先跑这个，退出码 0 才算"完成"
uv run python scripts/check.py
```

开新任务时的固定动作：

1. 复制 `specs/_template/` → `specs/002-<短名>/`，填 `spec.md` 的 DoD 与 scope 块；
2. 把 `specs/CURRENT` 改成 `002`（不改则 `guard scope` 会跳过范围校验）；
3. 只动 scope 内的文件，做完把 check.py 输出贴进 `tasks.md`。

## 已知坑

- `AGENT.md`（单数）不是标准文件名，Claude Code / Codex / Gemini CLI 默认只找 `AGENTS.md`——改名后才自动生效。
- Windows 上 `pnpm` 是 `.cmd`，`subprocess` 必须经 shell 启动，否则 `FileNotFoundError`（见 `scripts/check.py` 的 `run()`）。
- `vitest` 不加 `--run` 会进 watch 模式把终端卡死；CI 里要写成 `pnpm run test:unit -- --run`。
- `ruff format --check` 与 `ruff check` 是两道独立门，格式过了不代表 lint 过。
- Windows 控制台代码页是 936，Python 直接 `print` 中文源码片段会 `UnicodeEncodeError`；`scripts/guards.py` 已统一 UTF-8 输出、按 `utf-8-sig` 读文件（BOM 一起吃掉），新脚本照这个抄。
- 本机 `github.com` / `raw.githubusercontent.com` 被解析到 127.0.0.1 无法访问；取文件走 jsDelivr 镜像（`gcore.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}`），列目录走 `data.jsdelivr.com`。`web_search` 也会超时。

## 未决问题

- 前端 e2e（Playwright）尚未接入 `check.py`。
- 后端还没有 `repositories/` 层与数据库迁移，`rules/backend.md` 里的数据访问约定暂时无代码可对照。
- `guard forbidden` 目前不拦"注释掉的断言"，这个规则仍靠人看 diff。