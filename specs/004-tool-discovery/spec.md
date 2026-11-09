# 004 — 工具发现与只读配置

> 输入：`docs/task-plan.md` 的 004 卡；`docs/requirements.md` F-01 / F-02；`docs/decisions.md` ADR-002 / ADR-003 / ADR-006 / ADR-007 与附录 A / B；`specs/003-local-infra/spec.md`。
> 依赖：003 已完成（统一错误、路径、脱敏、请求层与应用壳可用）。
> 本卡只发现与读取工具配置，不写任何工具文件。

## 开卡决策（2026-11-09，用户确认）

1. **扫描结果不落 SQLite**：004 每次请求按需读取配置文件，纯内存组装；不新增迁移 / 缓存表。003 中「索引 / 缓存表由 004 追加」的默认预期顺延到确有性能需要的卡（最早 017）。
2. **前端新增 `/tools` 路由**：保留 `/` 首页与 `App.spec.ts` 现有 `backend: ok` 行为；004 的列表 / 详情在 `/tools` 独立验收，微信式主界面入口由 005 决定。
3. **不执行 CLI `--version`**：`detect` 不启动子进程；`version` 字段保留在响应模型中，004 恒为 `null`，真实版本探测留给 009 / 013 或后续卡。扫描因此无副作用、无 PATH / 超时差异。

## 背景与目标

1. F-01 / F-02 是 P0 闭环的第一块业务：用户打开应用就要看到「装了哪些 AI 工具、各自是否配置、当前用的什么供应商 / 地址 / 模型」，且密钥全程脱敏、读取不写盘。
2. 003 已提供统一错误、跨平台路径、脱敏函数、前端请求层与应用壳；004 只需新增适配器、只读服务与最小界面，不再重复造基础设施。
3. 适配器按 ADR 附录 A 的最小只读子集落地；006 / 008 / 012 / 013 再扩展写、会话、启动能力。新增适配器不得修改已有适配器行为。

目标（按优先级）：

1. 适配器协议 + 显式注册表；单工具失败被隔离为 warning，不影响其他工具。
2. Claude Code / Codex CLI 两个只读适配器，fixture 覆盖已配置、未配置、损坏、未知结构、权限不足。
3. `GET /api/tools` 与 `GET /api/tools/{tool_id}`；响应无明文密钥，读取前后文件 hash 不变。
4. 前端 `/tools` 最小列表 + 详情，状态、字段、warnings、空状态与错误态可用。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- 适配器与注册表：
  - 新增 `app/adapters/`：协议 + Claude Code + Codex CLI + 显式注册表；不动态加载插件。
  - `detect()` / `read()` 只读；共享 contract test 对 fixture 目录做读取前后 hash 对比，并断言重复调用结果一致。
  - 单个适配器抛未知异常时，列表仍返回 200，其他工具正常，整体结果含 `{code, message}` warning，不出现 traceback。
  - 未注册工具 / 未知目录结构忽略并记 warning；不因未知内容整体失败。
- 安装 / 配置状态：
  - 已安装判定 = 配置目录存在 或 对应可执行文件在 PATH（`which` 可注入）；已配置 = 至少解析到一个托管字段。
  - 未安装的工具不出现在列表中；已安装未配置的工具必须出现，`status = "unconfigured"`。
  - 解析成功 `status = "ok"`；损坏 / 无权限 / 未知格式 `status = "error"`，同一条目仍尽量展示已读出的字段与具体原因。
- Claude Code 适配器：
  - 配置目录优先 `CLAUDE_CONFIG_DIR`，否则 `~/.claude`；用户级配置文件 `settings.json`。
  - 读取供应商、接口地址（`env.ANTHROPIC_BASE_URL`）、模型（`model` / `env.ANTHROPIC_MODEL`）、是否第三方中转、最后修改时间、密钥（`env.ANTHROPIC_AUTH_TOKEN` 或 `env.ANTHROPIC_API_KEY`，脱敏）。
  - 不读取 OAuth / 登录凭据；不读取项目级 `.claude/` 配置。
  - fixture 覆盖已配置、未配置、坏一个字符、空文件、未知结构、权限不足。
- Codex CLI 适配器：
  - 配置目录优先 `CODEX_HOME`，否则 `~/.codex`；`config.toml` + `auth.json`。
  - 读取 `model`、`model_provider`、`[model_providers.<id>]` 的 `name` / `base_url` / `wire_api`、最后修改时间、`auth.json` 的 `OPENAI_API_KEY`（脱敏）。
  - `model_provider` 指向不存在的 provider、`wire_api` 未知、TOML 损坏、已安装未配置均有可读结论。
  - 不读取 OAuth token；`env_key` 只作为提示（密钥在环境变量中，本应用不读取）。
- 解析失败模型：
  - warning 为 `{code, message}`，code 至少覆盖 `PARSE_ERROR` / `PERMISSION_DENIED` / `UNKNOWN_FORMAT` / `UNSUPPORTED_VERSION` / `CONFIG_EMPTY` / `NO_MANAGED_FIELDS` / `SECRET_IN_ENV` / `ADAPTER_ERROR`。
  - JSON / TOML 语法错误给出文件、行 / 列与简短原因；消息不得回显文件内容，避免把密钥带进错误。
  - 空文件 / 只有未知字段 → `unconfigured` + warning，不误报为损坏。
  - 未知版本：顶层 `schema_version` 超出支持范围，或 Codex `wire_api` 未知 → `UNSUPPORTED_VERSION`；不按旧格式猜测字段。
- 第三方中转判定（无网络请求）：
  - Claude Code：无 `base_url` 或 host 为 `api.anthropic.com` → 官方；其余 host → 第三方。
  - Codex CLI：`model_provider = "openai"` 且无 `base_url` 或 host 为 `api.openai.com` → 官方；其余 provider / host → 第三方。
  - 判定结果写入 `is_third_party`；无法判定时为 `null`，界面显示「未知」。
- 响应模型（Pydantic，字段至少包含）：
  - `ToolView`：`id`、`display_name`、`status`、`installed`、`configured`、`version`、`provider`、`base_url`、`model`、`is_third_party`、`config_path`、`last_modified`、`has_secret`、`secret_preview`、`warnings`、`capabilities`。
  - `capabilities`：004 中 `read = true`，`write` / `sessions` / `launch = false`，`write_mode = "none"`；由后续卡按实际能力更新。
  - `ToolListResponse`：`{tools: [...], warnings: [...]}`；时间带时区 ISO 8601。
- 密钥脱敏与序列化：
  - 统一调用 `app.core.redaction.redact_secret` / `redact_text`；响应只含 `has_secret: bool` 与 `secret_preview`（脱敏值），不提供完整密钥入口。
  - 列表 / 详情 / 错误响应 / 日志的完整序列化结果都不含 fixture 明文 key；坏文件里带 key 时同样不泄露。
- API：
  - `GET /api/tools` 返回列表；`GET /api/tools/{tool_id}` 返回单个工具。
  - 未知 ID → 404 `{code: "TOOL_NOT_FOUND", message}`；`api/` 不手写 `HTTPException`。
  - 端点用同步 `def` 执行文件读取，由 FastAPI 线程池承载，避免阻塞事件循环。
  - 读取前后目标文件 hash 与目录清单不变；连续调用幂等，无新增缓存 / 临时文件。
- 前端：
  - 新增 `/tools` 路由与「工具」入口；`/` 首页与 `App.spec.ts` 现有断言保持通过。
  - 列表展示状态徽章（正常 / 未配置 / 异常，加载时「检测中」）、名称、供应商、模型；详情展示接口地址、是否第三方中转、脱敏密钥、最后修改时间、配置路径、warnings。
  - 空状态、加载态、请求失败态可读；部分失败时其他工具仍展示，warning 可见。
  - 所有请求走 `src/api/tools.ts`，组件无直接 `fetch`；类型显式，无 `any`。
  - Vitest 覆盖列表成功 / 详情 / 未配置 / 异常 / 空列表 / 请求失败；用 `getByRole` / `getByText` 断言。
- 文档与依赖：
  - `README.md` 补充 `/api/tools`、`/tools` 页面、`CLAUDE_CONFIG_DIR` / `CODEX_HOME` 本地验收方式；`PROGRESS.md` 交接更新。
  - 本卡不新增第三方依赖；TOML 用标准库 `tomllib`，JSON 用标准库。

## 范围

```scope
backend/src/**
backend/tests/**
frontend/src/**
README.md
```

- `backend/src/**`：新增 `app/adapters/`（协议 / 注册表 / Claude Code / Codex CLI）、`app/schemas/tool.py`、`app/services/tool_discovery.py`、`app/api/tools.py`；在 `app/main.py` 挂载路由。不改动 003 已实现的 core 行为。
- `backend/tests/**`：适配器 fixture（`tests/fixtures/tools/**`）、适配器单测、服务隔离测试、API 集成测试、读取只读 / 脱敏断言。
- `frontend/src/**`：`api/tools.ts`、`stores/tools.ts`、`views/ToolsView.vue` 及必要子组件、`router/index.ts` 的 `/tools` 路由、`App.vue` 的「工具」入口、对应 Vitest。
- `README.md`：接口、页面与本地验收说明。
- 不改 `backend/pyproject.toml` / `backend/uv.lock` / `frontend/package.json` / `frontend/pnpm-lock.yaml`（本卡无新依赖）；不改 `docs/**`、`rules/**`、`scripts/**`、其他任务卡；不改 003 的既有断言。
- `specs/**` 由 guard 固定放行；本卡只改本目录与 `specs/CURRENT`。

## 边界用例（实现时必须想到）

1. 一个工具都没安装：`GET /api/tools` 返回 200 空列表，前端显示空状态与引导，不报错。
2. Claude 已配置 + Codex 已安装未配置：两个条目同时出现且 `status` 不同。
3. 某份配置坏一个字符：只有该条目 `error` 并给出行 / 列；另一个工具仍正常。
4. 空文件或只有未知字段：判为 `unconfigured` + warning，不误报 `PARSE_ERROR`。
5. 配置文件不存在但有可执行文件：`unconfigured`；配置目录存在但无可执行文件：仍视为已安装。
6. 权限不足（用 monkeypatch 模拟 `PermissionError`）：该条目 `error` + `PERMISSION_DENIED`，列表不崩。
7. 环境变量覆盖：`CLAUDE_CONFIG_DIR` / `CODEX_HOME` 为空串时回退默认；相对路径按 home 解析；指向文件而非目录时不崩。
8. 类型异常：`env` 不是对象、`model_providers` 条目不是表、`model` 不是字符串 → `UNKNOWN_FORMAT`，不猜测字段。
9. 密钥：缺失时 `has_secret = false`；长度 ≤ 8 时 `secret_preview = "****"`；损坏文件里带明文 key 时，响应与日志都不得出现该 key。
10. 配置在两次请求之间被修改：下一次请求反映新 mtime / 新值；确保没有隐式缓存。
11. 重复 / 并发调用：列表与详情幂等，读取不加锁、不写盘、不产生临时文件。
12. 文件在 detect 与 read 之间被替换或删除：按读取失败降级为 `error`，不抛未捕获异常。
13. 适配器未知异常：整体 200，坏工具不出现在列表，`warnings` 含 `ADAPTER_ERROR` 与该工具名。
14. 未知 `tool_id`：404 `{code, message}`，不返回 traceback 或文件内容。

## 不做（明确划界）

- 不写任何工具文件；不实现快照、回滚、切换、预览、档案、绑定（006–008）。
- 不新增 SQLite 迁移、索引或缓存表（本卡按开卡决策 1 执行）。
- 不执行 CLI 子进程（包括 `--version`）、不发起网络请求、不调用模型。
- 不读取 / 解析 OAuth 登录态、keyring、系统凭据；密钥只来自配置文件或 `auth.json`。
- 不做动态插件加载、任意目录扫描、项目级 `.claude/` / `.codex/` 配置读取。
- 不实现健康体检（009）、会话回放（012）、启动器（013）、搜索筛选（010）。
- 不做微信式主界面（005）、主题外观（011）、桌面壳（015）。
- 不新增 Gemini CLI / OpenCode 等适配器（020）。
- 不修改 `requirements.md` 的边界与明确不做事项。