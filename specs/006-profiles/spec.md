# 006 — 供应商档案与模型清单

> 输入：`docs/task-plan.md` 的 006 卡；`docs/requirements.md` F-03 / N-1 / N-5 / N-8；`docs/decisions.md` ADR-002 / ADR-003 / ADR-006 / ADR-007 与附录 B；`specs/004-tool-discovery/spec.md`；现有 `GET /api/tools`、`frontend/src/api/client.ts` 与 005 主界面。
> 依赖：004 已完成（工具发现、状态推导、`GET /api/tools`、前端请求层可用）。
> 本卡只建立应用侧档案库与工具绑定关系，**不写任何工具配置文件**；预览、应用、快照、回滚属于 007 / 008。

## 开卡决策（2026-11-10）

1. **绑定不校验协议兼容性（用户确认）**：档案只声明一种协议（`anthropic` / `openai`）。006 允许同一份档案绑定到任意已发现工具，只记录「工具 → 档案」选择，不写工具文件；协议是否适配由 008 在 `plan` / 预览时明确拦截。界面必须标注「已绑定，尚未应用」，不得显示成已生效。这样 F-03「一份档案复用到两个工具」可在 006 验收。
2. **密钥存储按 ADR-006 落地**：006 引入 Python `keyring` 依赖，优先 OS keyring（Windows Credential Manager / macOS Keychain / Linux Secret Service）；不可用时回退 `<data>/secrets.json`（Unix `0600`），界面明确提示回退。测试注入假 SecretStore，不触碰真实系统钥匙串。
3. **档案与绑定落 `profiles.json`**：按 ADR-007 放在应用数据根目录，可读 JSON、原子写、文件锁；不随 `db/app.sqlite3` / `cache/` / `logs/` 删除，SQLite 不新增业务表。
4. **前端新增 `/profiles` 页面**：顶部导航增加「档案」；列表 / 新建 / 编辑 / 复制 / 删除占用提示 / 绑定面板都在该页。HomeView 主界面本卡不改；好友详情里展示当前档案留给 008。
5. **允许草稿态**：档案可以暂时不设置密钥、模型清单可以为空；界面分别提示「未设置密钥」「尚未添加模型」。重复模型（去空白后完全相同）拒绝保存并指出重复项，不静默去重。协议与 `base_url` 仍为必填且必须合法。
6. **删除保护**：`DELETE` 未带确认时，若档案被任何工具绑定（含已不可用工具），返回 409 `PROFILE_IN_USE`，message 列出占用方；结构化占用列表由 `ProfileView.used_by`（列表 / 详情）提供，前端用它展示确认框。带 `confirm=true` 才删除档案、解除全部绑定并清理密钥。
7. **绑定语义**：`PUT /api/tools/{tool_id}/profile` 只写 `profiles.json`；每个工具至多一个绑定；重复绑定同一档案幂等。解除绑定不清除工具里已经生效的配置（006 本来也不会写入），界面不得暗示已回滚。

## 背景与目标

1. F-03 是 P0 闭环的第二块业务：档案是「供应商 + 地址 + 凭证引用 + 模型清单」的可复用模板，与工具解耦；同一档案可服务多个工具，同一工具可在多档案间选择。
2. 004 已能发现工具并读取当前配置；006 建立应用侧档案库与绑定关系，为 007 的快照 / 008 的显式切换提供配置来源。
3. 密钥与档案物理分离：`profiles.json` 只存 `SecretRef`；密钥在 OS keyring 或 0600 回退文件中；响应 / 日志 / 错误 / 列表序列化都不含明文。

目标（按优先级）：

1. `Profile` / `SecretRef` / `ModelEntry` / `ToolBinding` 模型与 `profiles.json` 持久化（含损坏降级）。
2. 档案 CRUD、复制、模型清单、删除保护、绑定关系 API。
3. 前端 `/profiles` 管理页；凭证回退提示；绑定「尚未应用」诚实可见。
4. 文档：存储位置、备份、`keyring` 依赖理由与回退说明。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- 领域模型与存储：
  - `Profile`：`id`（UUID4 字符串）、`name`、`protocol`（`anthropic` / `openai`）、`base_url`、`secret_ref`（可空）、`models`（`ModelEntry` 列表）、`created_at` / `updated_at`（带时区 ISO 8601）。档案不含任何明文字段。
  - `SecretRef`：`id`、`backend`（`keyring` / `file`）、`locator`；`profiles.json` 只存引用，不存密钥。`locator` 按 ADR-006 使用 `profile_id`。
  - `ModelEntry`：`id`（模型标识）、`display_name`（可空）；`id` 去空白后非空、最长 120；重复按 `id` 精确比较拒绝。
  - `ToolBinding`：`tool_id`、`profile_id`、`bound_at`、`active`（006 恒为 `false`）、`applied_at` / `snapshot_id`（006 为 `null`）；每个 `tool_id` 至多一条。
  - `profiles.json` 根结构 `{schema_version: 1, profiles: [...], bindings: [...]}`；缺失文件视为空库；JSON 损坏 / 结构非法 / `schema_version` 不支持 → 可读 `PROFILE_STORE_UNREADABLE` / `PROFILE_STORE_VERSION_UNSUPPORTED`，**不得覆盖原文件**。
  - 写入复用 `app/core/atomic.write_json_atomic` 与 `app/core/locks.FileLock`；写操作在锁内完成「重新读取 → 业务变更 → 原子写」，覆盖密钥与档案的整个事务，避免并发丢更新；锁超时返回可读错误，不产生半截文件。
  - 读取不创建 / 不修改文件；连续列表 / 详情调用幂等，文件 hash 不变。
  - `profiles.json` 不随 `db/app.sqlite3`、`cache/`、`logs/` 删除而丢失；测试删除索引文件后重新加载仍能看到档案。
- 密钥存储：
  - 新增 `SecretStore` 边界（Protocol / 抽象）：`status()`、`get(ref)`、`put(profile_id, secret) -> SecretRef`、`delete(ref)`；服务层只依赖该边界，测试注入假实现。
  - `keyring` 写入 `backend/pyproject.toml` 与 `backend/uv.lock`；理由：跨平台 OS 凭据库、避免明文落盘、无需自研系统 API；只允许 `keyring` 及其必要平台依赖的 lock 变化，不顺带升级无关包。
  - 读取按 `SecretRef.backend` 路由（旧的 file 引用在 keyring 恢复后仍可读）；写入使用当前可用后端。
  - keyring 可用时 `backend="keyring"`、`fallback=false`；不可用时使用 `<data>/secrets.json`，Unix 权限 `0600`，`backend="file"`、`fallback=true` 且返回可读 message；界面显示非阻塞 banner，不静默降级。两者都不可用 → `backend="unavailable"`、`SECRET_STORE_ERROR`，相关写操作拒绝并给出原因。
  - 在 `Settings` 增加 `secret_backend` 设置，读取环境变量 `CC_ROSTER_SECRET_BACKEND`（`auto|keyring|file`，默认 `auto`）：`file` 用于手动验收回退 banner；显式 `keyring` 在不可用时返回可读错误而不是静默回退。
  - 创建 / 更新带密钥时写入 SecretStore；更新时省略 `secret` = 保持原密钥，显式 `null` = 清除，字符串 = 替换；删除档案时清理密钥。两步写入失败要有补偿：密钥写成功但档案保存失败时回滚新密钥；不得留下无提示的半状态。
  - 响应只含 `has_secret: bool`、`secret_preview`（ADR-006 三档）与 `secret_backend`；不暴露 `locator`，不存在完整密钥查看 / 导出入口。密钥引用存在但读取不到时 `has_secret=false` + `SECRET_MISSING` warning；不得让整个列表失败。
  - 列表 / 详情 / 错误响应 / 日志的完整序列化不含 fixture 明文密钥（用假 key 全链路断言）。
- API：
  - `GET /api/profiles`：`{profiles: ProfileView[], bindings: BindingView[], secret_store: SecretStoreStatus, warnings: []}`；`ProfileView` 含 `used_by: ToolRef[]`（工具已卸载时 `installed=false`，仍参与删除保护）与 `warnings: ProfileWarning[]`。
  - `POST /api/profiles`（201，返回 `ProfileView`）、`GET /api/profiles/{profile_id}`（200）、`PATCH /api/profiles/{profile_id}`（200）、`POST /api/profiles/{profile_id}/copy`（201）、`DELETE /api/profiles/{profile_id}?confirm=true`（200，`ProfileDeleteResponse`）。
  - `PUT /api/tools/{tool_id}/profile`（body `{profile_id}`，200，`BindingView`）；`DELETE /api/tools/{tool_id}/profile`（200，`BindingDeleteResponse`，幂等）；绑定端点不写工具文件。
  - `ProfileDeleteResponse`：`{deleted: bool, unbound_tools: ToolRef[]}`；`BindingDeleteResponse`：`{tool_id: str, removed: bool}`。全部是 Pydantic 模型，不使用裸 dict。
  - 校验：名称去空白后 1–80 字符、大小写不敏感唯一；`base_url` 必须是绝对 `http` / `https` URL、有 host、不含用户名 / 密码 / fragment，最长 2048；`protocol` 枚举；模型 `id` 去空白后 1–120；重复模型返回 422 `VALIDATION_ERROR` 且 message 指出重复项。
  - 业务错误码至少覆盖：`PROFILE_NOT_FOUND`（404）、`PROFILE_NAME_CONFLICT`（409）、`PROFILE_IN_USE`（409）、`PROFILE_STORE_UNREADABLE`（500）、`PROFILE_STORE_VERSION_UNSUPPORTED`（500）、`SECRET_STORE_ERROR`（500）、`TOOL_NOT_FOUND`（404，复用 004）；格式错误走统一 422 `VALIDATION_ERROR`，message 不回显原始输入值。
  - `api/` 只做参数校验 + 转发 service；不写业务逻辑、不拼 dict、不手写 `HTTPException`。`services/` 不直接依赖 `fastapi.Request`；`repositories/` 不 import `services/`。
  - 未知 `tool_id` / 未安装工具绑定 → 404；档案不存在 → 404；重复解绑 → 200 `removed=false`；重复绑定同一档案 → 结果不变、`bound_at` 不变。
- 复用与删除保护：
  - 同一档案可绑定 `claude-code` 与 `codex-cli` 两个工具（按开卡决策 1，不校验协议）；两个工具都出现在 `used_by`。
  - 同一工具重新绑定另一档案：只保留新绑定；旧档案 `used_by` 不再包含该工具。
  - 删除被占用档案未确认 → 409 `PROFILE_IN_USE`；message 含占用方名称；占用方的结构化列表由 `GET /api/profiles/{id}` / 列表的 `used_by` 提供（错误信封仍保持 `{code, message}`）；确认后删除档案、全部绑定与密钥；工具配置文件 hash 不变。
  - 复制档案：新 UUID、新时间戳；复制协议 / 地址 / 模型 / 密钥；不复制绑定；名称可由请求指定，未指定时自动生成不冲突的「原名 (副本)」/「原名 (副本 2)」…。
  - 绑定 / 解绑 / 档案 CRUD 前后，工具配置目录与文件 hash 完全不变（N-2）。
- 前端：
  - 新增 `/profiles` 路由与顶部「档案」入口；`App.vue` 导航可见；HomeView 与 `/tools` 行为不变。
  - `src/api/profiles.ts`：显式类型、全部经 `requestJson`、无 `any`；`src/stores/profiles.ts`：列表 / 绑定的 latest-wins、loading / fatal error / refreshError 语义与 `stores/tools.ts` 一致。
  - 页面：档案列表（名称、协议、地址、模型数、密钥状态 / 脱敏预览、占用工具）；空状态 + 新建入口；加载骨架 / 错误 + 重试；刷新失败保留旧数据并提示；`SECRET_MISSING` / `SECRET_STORE_ERROR` warning 可见，不能伪装成「未设置密钥」。
  - 表单：明确分区「档案配置」（名称 / 协议 / 地址 / 模型）与「凭证」（密钥）；编辑时密钥留空 = 保持，提供显式「清除密钥」；不显示完整密钥；后端 422 / 409 的 message 原样可读展示。
  - 模型编辑器：增删改、空清单提示、重复模型即时提示；保存时以后端结果为准。
  - 复制按钮；删除确认框展示 `used_by`，取消零变化；确认后只在 API 成功时提示成功；不得出现假成功。
  - 绑定面板：列出已发现工具与当前绑定，可绑定 / 解除；明确显示「已绑定，尚未应用（切换在 008 实现）」；解除绑定不得暗示已回滚工具配置；已卸载但仍有绑定的工具单独列出并标注「已不可用」。
  - 密钥回退 banner：`secret_store.fallback=true` 时可见；`backend="unavailable"` 时以错误样式展示并说明写操作不可用。
  - 可访问性：表单 label、按钮、dialog role、focus 可见；Vitest 用 `getByRole` / `getByText`；单文件超过 ~150 行拆分组件 / composable；按需扩展 `__tests__/dom.ts` 的原生角色映射（textbox / combobox / dialog / checkbox），不新增测试依赖。
  - Vitest 覆盖：列表 / 空态 / 加载 / 错误 / 刷新失败、新建校验、编辑保持 / 清除密钥、模型增删改 / 空清单 / 重复、复制、删除被占用 → 确认 / 取消、绑定 / 解绑与「尚未应用」、回退 banner、无完整密钥。
- 文档与依赖：
  - `README.md`：新增 `/profiles` 页面、API、`profiles.json` / `secrets.json` 位置与备份说明、`keyring` 依赖理由与回退行为、手动验收方式；更新「当前状态」与「本地数据目录」。
  - `PROGRESS.md`：开卡决策、实现交接与「下一个可执行命令」。
  - 除 `keyring` 外不新增依赖；不新增前端依赖；`uv.lock` 同步；不改 `pnpm-lock.yaml`。
  - 手动验收：真实 keyring（Windows Credential Manager）写入 / 删除、`CC_ROSTER_SECRET_BACKEND=file` 回退 banner、占用删除、复制、重启持久化；记录实际结果。

## 范围

```scope
backend/src/**
backend/tests/**
backend/pyproject.toml
backend/uv.lock
frontend/src/**
README.md
```

- `backend/src/**`：新增 `app/schemas/profile.py`、`app/repositories/profiles.py`、`app/repositories/secrets.py`、`app/services/profile_service.py`、`app/api/profiles.py`，在 `app/main.py` 挂载路由；在 `app/core/config.py` 增加 `secret_backend` 设置（读取 `CC_ROSTER_SECRET_BACKEND`）；复用 `app/core/` 的时钟 / 原子写 / 文件锁 / 脱敏 / 错误。
- `backend/tests/**`：模型校验、仓储 / 损坏 / 并发、SecretStore（假 keyring + 文件回退）、API 集成、只读与脱敏断言。
- `backend/pyproject.toml`、`backend/uv.lock`：仅新增 `keyring` 依赖及必要平台依赖。
- `frontend/src/**`：`api/profiles.ts`、`stores/profiles.ts`、`views/ProfilesView.vue` 及子组件、`router/index.ts` 的 `/profiles` 路由、`App.vue` 导航、`__tests__/dom.ts` 角色映射、Vitest。
- `README.md`：页面、接口、存储 / 备份、keyring 与回退、手动验收。
- 不改 `backend/src/app/adapters/**` 的既有行为、`GET /api/tools` 响应与 004 断言；不改 `frontend/src/views/HomeView.vue` / `ToolsView.vue` 行为；不改 `docs/**`、`rules/**`、`scripts/**`、`frontend/package.json`、`frontend/pnpm-lock.yaml`。
- `PROGRESS.md`、`specs/**` 由 guard 固定放行；本卡只改本目录、`specs/CURRENT` 与交接记录。

## 边界用例（实现时必须想到）

1. `profiles.json` 不存在：返回空列表，不创建文件、不报错。
2. `profiles.json` 是坏 JSON / 顶层不是对象 / `profiles` 或 `bindings` 不是列表 / `schema_version` 缺失或大于 1：可读错误，原文件与 hash 不变；修复后重启可恢复。
3. 名称为空 / 全空白 / 超长 / 与现有名称仅大小写不同：拒绝并说明；更新时排除自身。
4. `base_url` 缺 scheme、非 http(s)、无 host、带用户名密码、带 fragment、超长：拒绝；合法带端口 / 路径的地址保留原样，不做隐式改写。
5. 模型：空清单可保存并提示；模型 id 空 / 超长 / 重复（去空白后精确相同）拒绝；`display_name` 空串归一为 `null`。
6. 档案无密钥：可保存，`has_secret=false`；带密钥创建 / 编辑、编辑留空保持、显式清除、删除档案清理密钥。
7. keyring 不可用：回退文件并显示 banner；`secrets.json` 在 Unix 为 `0600`；keyring 写失败不静默改文件；两处都不可用 → 可读错误，相关写操作拒绝。
8. `secret_ref` 存在但 keyring / 文件条目被外部删除：`has_secret=false` + `SECRET_MISSING` warning，列表继续可用。
9. 删除被占用档案：未确认 409 + 占用方；确认后删除；工具配置 hash 不变；已卸载工具的绑定仍算占用。
10. 同一工具重复绑定同一档案幂等（`bound_at` 不变）；绑定另一档案替换旧绑定；解绑不存在的绑定返回 200 `removed=false`。
11. 绑定未知 / 未安装工具、未知档案：404；不写工具文件、不产生临时文件。
12. 并发创建同名档案 / 并发更新同一档案：文件锁串行化，最多一个成功或后写者看到最新数据；文件始终是合法 JSON，不丢更新。
13. 写 `profiles.json` 失败（权限 / 磁盘）：原文件不变；密钥写入有补偿；返回可读错误，不显示成功。
14. 复制：带密钥复制、无密钥复制、密钥读取失败（降级为不带密钥 + `SECRET_MISSING` warning）、名称冲突自动后缀；不复制绑定。
15. 请求带未知字段 / 类型错误：422 `VALIDATION_ERROR`，message 不含原始密钥；`api/` 不手写 `HTTPException`。
16. 100 份档案 / 100 条绑定：列表接口与页面可用，无 N+1 文件读取；本卡不做虚拟滚动，但不得卡死。
17. 前端：创建 / 编辑 / 删除 / 绑定的失败、取消、重复点击；刷新失败保留旧数据；回退 banner；键盘操作；窄窗口不横向滚动。

## 不做（明确划界）

- 不写任何工具配置文件；不做 `plan` / `render` / `verify` / 快照 / 回滚 / 一键切换（007、008）。
- 不做健康体检（009）、会话历史（012）、启动器（013）、应用内对话（014）、搜索筛选（010）、独立外观（011）。
- 不从现有工具配置自动导入档案；不读取工具配置里的密钥来预填表单。
- 不提供完整密钥查看 / 导出 / 明文下载；不做云同步、账号体系、共享密钥、API 转售。
- 不新增 SQLite 业务表 / 迁移；不引入 ORM；不改 `bootstrap_database` 的既有行为。
- 不改 004 的 `GET /api/tools` 响应与断言；不改 HomeView / ToolsView 的既有行为。
- 不在本卡做「当前档案」在好友详情 / 主界面的展示；留给 008。
- 不新增前端依赖 / UI 库；不改 `pnpm-lock.yaml`。
- 不修改 `requirements.md` 的边界与「明确不做」事项。