# 003 — 本地应用基础设施

> 输入：`docs/task-plan.md` 的 003 卡；`docs/decisions.md` 的 ADR-001 / ADR-005 / ADR-006 / ADR-007。
> 依赖：002 已完成（决策与契约已成文）。
> 本卡只搭基础设施与最小应用壳，不实现任何工具业务功能。

## 背景与目标

1. 002 已拍板项目名、数据目录、密钥存储、本地 Web 形态与错误 / 日志约定；003 把这些决策落成后续卡可直接复用的基础设施，避免 004–008 各造一套。
2. 统一错误模型、带时区时钟、跨平台数据目录、SQLite 索引与幂等迁移、原子写与文件锁、日志脱敏、前端请求层与应用壳，是 P0 闭环的共同地基。
3. 本卡完成后，004 可以只关心「发现工具、解析配置」，不必再处理路径、错误响应、日志脱敏与请求封装。

目标（按优先级）：

1. 后端所有错误响应统一为 `{code, message}`，未知异常不外泄内部细节或密钥。
2. 按 ADR-007 解析数据目录；SQLite 可删可重建；JSON 落盘原子化；文件锁可用。
3. 按 ADR-006 建立统一脱敏函数与日志过滤器，用假 key 做全链路断言。
4. 前端组件不再直接 `fetch`；请求层、路由、Pinia store 与应用壳就绪。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- 错误模型：
  - `AppError(code, message)` 经全局处理器返回 `{"code", "message"}`；业务异常 / Pydantic 校验失败 / 框架 404 / 405 / 未知异常都有稳定 code。
  - 未知异常返回 500 `INTERNAL_ERROR`，响应不含 traceback、绝对路径或异常原文；`api/` 内不再手写 `HTTPException`。
  - 错误消息经过统一脱敏后才写入响应。
- 时钟与路径：
  - 时钟函数返回带时区（UTC）的 `datetime`；测试不依赖本机时区。
  - `resolve_data_dir()` 在 Windows / macOS / Linux 分别得到 ADR-007 表中的路径；测试用 `PureWindowsPath` / `PurePosixPath` 覆盖三分支，不依赖运行平台。
  - 数据根目录、`db/`、`logs/` 可被安全创建；目录已存在时幂等。
- 存储基础设施：
  - SQLite bootstrap 设置 WAL、busy timeout、`PRAGMA user_version`；迁移可重入；删除 `db/app.sqlite3` 后重新 bootstrap 能重建。
  - `user_version` 比代码支持的新时明确报错，不降级、不猜测。
  - JSON 原子写使用同目录临时文件 + `os.replace`；写入失败时原文件保持不变，临时文件被清理。
  - 跨平台文件锁带超时；已持锁时第二次获取超时并返回可读错误，不无限阻塞。
  - 本卡只建迁移机制，不预建索引 / 缓存 / 审计业务表；这些表由 004 / 007 / 016 各自的卡追加迁移。
- 本地安全边界：
  - 默认监听 `127.0.0.1`，README 的启动方式不得出现 `0.0.0.0`。
  - CORS 只放行本地前端来源；非白名单来源拿不到 `Access-Control-Allow-Origin`。
  - 请求体超过上限（默认 1 MiB）返回 413 `{code: "PAYLOAD_TOO_LARGE", message}`。
- 日志与脱敏：
  - `redact_secret()` 按 ADR-006 的三档长度规则输出；边界 0 / 8 / 9 / 16 / 17 有测试。
  - 结构化日志同时写 stdout 与 `<data>/logs/`；格式化后的日志中不出现假 key 明文。
  - 用假 key 构造 `AppError` 时，HTTP 响应、日志、异常记录中都不出现明文。
- 前端：
  - `src/api/client.ts` 返回显式类型；HTTP 错误、网络错误、超时都归一为 `ApiError`（`code` / `message` / `status`）。
  - Vitest 覆盖成功、HTTP 错误、网络错误、超时四条路径。
  - 组件中无直接 `fetch`；`src/api/health.ts` 提供 `getHealth()`。
  - 路由、Pinia 基础 store、应用壳就绪；首页仍可观察到 `backend: ok`。
- 文档：
  - `README.md` 补充数据目录、loopback、日志位置与启动说明；`PROGRESS.md` 交接更新。
  - 本卡不新增第三方依赖；若必须新增，先在 spec 写理由并同步 `uv.lock` / `pnpm-lock.yaml`（AGENTS.md 第 5 条）。

## 范围

```scope
backend/src/**
backend/tests/**
frontend/src/**
README.md
PROGRESS.md
.gitattributes
```

- `backend/src/**`：`app/core/`（errors / clock / paths / db / atomic / locks / redaction / logging / security）、`app/api/` 的处理器接线、`app/main.py` 的 `create_app()`。
- `backend/tests/**`：上述行为的测试；测试路由只存在于测试进程。
- `frontend/src/**`：`api/client.ts`、`api/health.ts`、`stores/app.ts`、`router/index.ts`、`App.vue`、首页视图与测试；清理脚手架 `stores/counter.ts`。
- `README.md` / `PROGRESS.md`：启动说明与交接状态。
- 不改 `backend/pyproject.toml` / `backend/uv.lock` / `frontend/package.json` / `frontend/pnpm-lock.yaml`（本卡无新依赖）；不改 `frontend/vite.config.ts` / `vitest.config.ts` / `eslint.config.ts`（沿用相对导入与现有测试环境）；不改 `docs/**`、`rules/**`、`scripts/**`、其他任务卡。
- `specs/**` 由 guard 固定放行；本卡只改本目录与 `specs/CURRENT`。
- `.gitattributes`（仓库根，新增）：声明 `* text=auto eol=lf`。理由：Windows 版 git 默认 `core.autocrlf=true` 会把工作区 checkout 成 CRLF，而 WSL / Linux / CI 的 git 默认不做转换，`scripts/guards.py` 用 `git diff --name-only HEAD` 取改动清单时会把每个 CRLF 文件误判为"已修改"（实测在 WSL 里误报 12 个从未动过的文件越界）。本卡要在 WSL 里跑同一份验收，此文件是两端判定一致的前提，不涉及业务代码。

## 边界用例（实现时必须想到）

1. 错误响应：业务异常、Pydantic 校验失败、框架 404 / 405、未知异常、超限请求体都必须返回 `{code, message}`，不允许混入 `detail`。
2. 数据目录：`%LOCALAPPDATA%` / `XDG_DATA_HOME` 缺失时按 ADR 文档回退；平台值非法时明确报错，不静默用到错误目录。
3. SQLite：删除数据库文件、重复 bootstrap、`user_version` 超前、目录不可写四种情况都要有可读结果；不自动降级版本。
4. 原子写：目标文件已存在、写入中途失败、目标只读时，原文件不得被截断或写坏。
5. 文件锁：两个进程同时申请同一把锁时，后者超时返回可读错误；锁文件不残留为无限阻塞源。
6. 脱敏：空串、长度 8 / 9 / 16 / 17 的边界；`sk-...`、`Bearer ...`、`api_key=...` 等常见形态；日志格式化后仍无明文。
7. 前端请求：HTTP 非 2xx、响应不是 JSON、网络断开、超时、后端返回未知 `code` 时组件都不崩溃，只展示可读错误。
8. CORS：白名单来源的预检请求通过；非白名单来源不返回 `Access-Control-Allow-Origin`。
9. 重复调用：`getHealth()` 连续调用、应用重复挂载、`bootstrap_database()` 重复执行都保持幂等。

## 不做（明确划界）

- 不实现工具发现、适配器、供应商档案、快照、切换、体检、会话等业务功能（004–014）。
- 不预建索引 / 缓存 / 审计业务表；不实现全局只读模式（016）。
- 不落地 `SecretStore` 的 keyring / 文件后端，不引入 keyring 依赖；ADR-006 允许 003 先定义接口，本卡按最小范围把接口与实现留给 006。
- 不引入 ORM、Alembic、axios、第三方日志库或新依赖。
- 不做 Tauri 桌面壳（015）、微信式主界面（005）、主题外观（011）。
- 不发起任何外部网络请求；健康检查仍只返回本地状态。
- 不改 `requirements.md` 的边界与明确不做事项。