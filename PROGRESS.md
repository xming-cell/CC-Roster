# 进度

## 当前状态

- 骨架完成：后端 health 端点 + 1 个测试；前端调通 `/api/health`；`scripts/check.py` 七道门 + CI 打通。
- 工作流基线加固完成（任务卡 001）：规则已机器化，`check.py` 现在含 `guard scope` / `guard forbidden` 两步硬门禁。
- 根目录 `README.md` 已改写为「产品介绍 + 开发者上手」文档；该文件已在 001 卡 scope 中登记（同卡文档改动）。
- 已产出后续任务拆解初稿 `docs/task-plan.md`：覆盖 F-01～F-17 / N-1～N-11。
- 任务卡 002 完成：D-1～D-8 已拍板并写入 `docs/decisions.md`；适配器契约与领域模型成文；未写业务代码。
- 任务卡 003 完成（`specs/003-local-infra`，本地应用基础设施）：统一错误模型、带时区时钟与跨平台数据目录、SQLite bootstrap（WAL / `user_version` 幂等迁移）、原子 JSON 写与跨平台文件锁、请求体上限与 CORS 白名单、结构化日志与 ADR-006 三档脱敏、前端请求层 / 路由 / Pinia / 应用壳；README 已补数据目录、loopback、日志与启动说明。
- 换行符统一（已做，scope 已登记）：仓库根新增 `.gitattributes` 声明 `* text=auto eol=lf`。原因：Windows 侧 git（`core.autocrlf=true`）把工作区 checkout 成 CRLF，WSL / Linux / CI 的 git 默认不做转换，`scripts/guards.py` 用 `git diff --name-only HEAD` 取改动清单时把每个 CRLF 文件当成"已修改"，实测在 WSL 里误报 12 个从未动过的文件越界。同批改动里顺手删除了仓库根误建的 0 字节文件 `; done`（命令里的 `; done` 被 shell 当成重定向目标写出来，单独就能让 `guard scope` 失败）。
- 最近一次验收：见 `specs/003-local-infra/tasks.md` 的「验收记录」。

## 下一个可执行命令

```bash
# 1) 任何时候先跑这个，退出码 0 才算"完成"
uv run python scripts/check.py
```

开新任务时的固定动作：

1. 复制 `specs/_template/` → `specs/NNN-<短名>/`，填 `spec.md` 的 DoD 与 scope 块；
2. 把 `specs/CURRENT` 改成 `NNN`（不改则 `guard scope` 会跳过范围校验）；
3. 只动 scope 内的文件，做完把 check.py 输出贴进 `tasks.md`。

卡片状态：`specs/003-local-infra`（003 — 本地应用基础设施）已完成。下一张卡为 004（工具发现与只读配置），尚未建目录；开工时先复制 `specs/_template/` 并更新 `specs/CURRENT`。

## 已知坑

- `AGENT.md`（单数）不是标准文件名，Claude Code / Codex / Gemini CLI 默认只找 `AGENTS.md`——改名后才自动生效。
- Windows 上 `pnpm` 是 `.cmd`，`subprocess` 必须经 shell 启动，否则 `FileNotFoundError`（见 `scripts/check.py` 的 `run()`）。
- `vitest` 不加 `--run` 会进 watch 模式把终端卡死；CI 里要写成 `pnpm run test:unit -- --run`。
- `ruff format --check` 与 `ruff check` 是两道独立门，格式过了不代表 lint 过。
- Windows 控制台代码页是 936，Python 直接 `print` 中文源码片段会 `UnicodeEncodeError`；`scripts/guards.py` 已统一 UTF-8 输出、按 `utf-8-sig` 读文件（BOM 一起吃掉），新脚本照这个抄。
- CRLF 会让 `guard scope` 误报越界：Windows 侧 git 是 `core.autocrlf=true`（工作区 CRLF、仓库 LF），WSL / Linux 侧默认不转换，同一份工作区在两边判定不同。已由仓库根 `.gitattributes`（`* text=auto eol=lf`）固定；若仍在某台机器上看到成片 `M`（内容其实没变，是索引里的 stat 缓存过期），跑 `git read-tree HEAD` 重建索引即可。
- 本机 `github.com` / `raw.githubusercontent.com` 被解析到 127.0.0.1 无法访问；取文件走 jsDelivr 镜像（`gcore.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}`），列目录走 `data.jsdelivr.com`。`web_search` 也会超时。

## 未决问题

- 前端 e2e（Playwright）尚未接入 `check.py`。
- 后端还没有 `repositories/` 层；数据库迁移机制已在 003 就绪，但尚无业务表迁移，`rules/backend.md` 里的数据访问约定暂时无代码可对照。
- `guard forbidden` 目前不拦"注释掉的断言"，这个规则仍靠人看 diff。