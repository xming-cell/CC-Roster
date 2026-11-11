# 008 — 一键切换与改动预览

> 输入：`docs/task-plan.md` 的 008 卡；`docs/requirements.md` F-04 / F-05；N-2 / N-3 / N-4 / N-8 / N-10 / N-11；`docs/decisions.md` ADR-003 / ADR-004 / ADR-006 / ADR-007 与附录 A / B；006 的档案 / 绑定 / 密钥；007 的快照 / 写引擎 / 保真编辑；004 的 Claude Code 与 Codex CLI 适配器。
> 依赖：006、007 已完成。
> 本卡把 007 的写内核接到两个真实工具上，并提供预览 / 应用 / 冲突 / 审计 API 与主界面 UI；不改 004 的只读读取语义。

## 开卡决策（2026-11-11，用户确认）

1. **密钥写入工具配置**：预览中的密钥字段只显示脱敏值；apply 时把档案密钥写入 Claude Code `settings.json` 的 `env` 或 Codex CLI `auth.json` 的 `OPENAI_API_KEY`。API 响应、日志、错误、审计、预览 diff、快照 `meta.json` 一律不出现明文；快照只保存写入前原始字节，原始 blob 可能含旧密钥，但不提供任何下载入口。
2. **协议不匹配拦截**：Claude Code 只接受 `anthropic` 档案，Codex CLI 只接受 `openai` 档案；不匹配时预览返回 `PROTOCOL_MISMATCH` blocker，apply 零写入。
3. **模型选择**：预览默认使用档案模型清单第一项，可在预览中选择清单内其他模型；清单为空时保持工具当前模型不变。
4. **前端入口**：主界面好友详情内新增「切换档案」与「快照 / 回滚」区域；`/profiles` 的绑定面板保留，只把「尚未应用」改为真实状态，不复制切换 UI。
5. **无状态防漂移**：预览返回每个目标文件的观察值与 `preview_digest`；apply 必须回传二者。服务端重新读取、重新生成计划并比对 digest；文件内容变化交给 `WriteEngine` 的 `WRITE_CONFLICT`，档案或模型变化返回 `SWITCH_PREVIEW_STALE`。预览不落任何状态，也不创建快照 / 审计。
6. **诚实成功**：只有写引擎回读校验、审计、绑定保存都成功才返回成功；绑定保存失败时用本次预快照自动回滚，回滚也失败则明确返回 `APPLY_ROLLBACK_FAILED`，不得假成功。
7. **错误详情**：`ErrorResponse` 增加可选 `details`（仅冲突 / 过期文件使用），保持既有 `{code, message}` 响应不变；前端 `ApiError` 解析 `details` 显示冲突路径。
8. **Codex 映射**：使用内置 `openai` provider 覆盖（`model_provider = "openai"`，`[model_providers.openai]`），密钥写 `auth.json.OPENAI_API_KEY`；官方 host 用 `wire_api = "responses"`，第三方用 `"chat"`。真实 Codex 行为必须在 T1 / T8 手动确认；若版本不读 `auth.json`，先记录并调整映射，不静默失败。
9. **不新增依赖**：TOML 用已有 `tomlkit`，JSON / 文本编辑用 007 的 `format_edits.py`；前端不新增 UI 库。若实现确需新依赖，先改本卡 scope、理由与 lock。
10. **不做的边界**：不实现全局只读模式（016）、审计 UI（016）、健康体检（009）、新工具适配（020）、自动合并、后台自动同步。

## 背景与目标

1. F-04 要求「预览 → 确认 → 快照 → 写入 → 回读校验」是一次显式操作；取消时磁盘零变化；必须逐字段展示 before / after；必须说清重启要求。
2. F-05 要求任何写入前自动快照、回读不一致自动还原、外部改动拒绝覆盖、回滚逐字节一致；007 已交付这些内核，008 负责把适配器的 `plan` / `render` / `verify` 接上。
3. N-4 要求只改目标字段，注释 / 键序 / 未知字段原样保留；N-11 要求可读操作记录；N-10 要求重启 / 冲突 / 部分失败不得出现假成功。

目标（按优先级）：

1. 两个适配器的写契约：`plan` / `render` / `verify`，逐字段 before / after、目标文件、重启要求、blockers。
2. `POST /api/switch/preview`：只读预览，零落盘、零快照、零审计。
3. `POST /api/switch/apply`：防漂移 → 快照 → 原子写 → 回读校验 → 审计 → 绑定；失败自动还原。
4. 冲突 / 只读 / 无权限 / 格式不安全的可读返回；不自动合并。
5. 主界面预览确认框、快照列表 / pin / 回滚；档案页状态同步。
6. 审计 API、README、手动验收与 `check.py`。

## 验收标准（DoD）

### 适配器写契约（`backend/src/app/adapters/`）

- `ToolAdapter` Protocol 增加 `supported_protocols` 与 `plan` / `render` / `verify`；两个现有适配器都实现，未实现写能力的适配器仍可只读。
- `ToolCapabilities` 对 `claude-code` 与 `codex-cli` 变为 `write=true`、`write_mode="managed_fields"`；`GET /api/tools` 的响应随之变化，相关既有断言同步更新，理由写进 `PROGRESS.md`（行为变更，不是为让测试变绿）。
- `plan(profile, *, secret, model, current)` 是纯函数式的计划生成：不写盘、不发网络请求、不改全局状态；返回每个目标文件的 `path` / `format` / `edits` / 展示用 `changes`、`blockers`、`warnings`、`restart_required`、`restart_message`。
- `render(plan_file, original_bytes)` 纯函数、同输入同输出；`verify(plan_file, original_bytes, rendered_bytes)` 同时校验：
  - 每个 `set` 字段等于目标值、每个 `remove` 字段不存在；
  - 「未知内容」未被破坏：JSON / TOML 解析后移除托管路径，剩余结构深度相等；`key_value`（如未来使用）按非托管行顺序比较。
- 无法保证保真（重复键、非法格式、非 UTF-8、顶层不是对象 / 表、中间路径类型不符）→ `UNSAFE_WRITE`，不写盘、不猜。
- 共享一个 `ManagedFieldsAdapter` 风格的 helper 实现 `render` / `verify`，适配器只负责 `plan` 映射；不得在两个适配器里复制粘贴渲染逻辑。

#### Claude Code 映射

- 目标文件：`<CLAUDE_CONFIG_DIR 或 ~/.claude>/settings.json`；缺失时 apply 创建最小合法 JSON 对象。
- 托管字段：
  - `env.ANTHROPIC_BASE_URL = profile.base_url`，始终设置。
  - 模型：若选择了模型（显式选择或档案第一项），优先更新已存在的 `env.ANTHROPIC_MODEL`；否则更新已存在的顶层 `model`；两者都不存在时写 `env.ANTHROPIC_MODEL`。两者同时存在时更新 env 字段，顶层 `model` 原样保留并给 `MODEL_SHADOWED` warning（env 优先，与 004 读取语义一致）。
  - 密钥：若档案带密钥，优先更新已存在的 `env.ANTHROPIC_AUTH_TOKEN`；否则更新已存在的 `env.ANTHROPIC_API_KEY`；都不存在时，官方 `api.anthropic.com` 写 `ANTHROPIC_API_KEY`，第三方写 `ANTHROPIC_AUTH_TOKEN`。两个凭证字段同时存在时更新 `AUTH_TOKEN`，并把 `API_KEY` 的删除作为一条显式 change 展示。
  - 档案没有密钥：不增删任何凭证字段，返回 `PROFILE_SECRET_EMPTY` warning，预览显示「保留工具现有密钥」。
- blockers：JSON 解析失败 / 顶层不是对象 / `env` 不是对象 / `schema_version` 不受支持 / 文件无读权限 / 目标不可写 / 协议不匹配。
- 重启：`restart_required=true`，文案明确「Claude Code 需要重启后才会读取新的 settings.json」。

#### Codex CLI 映射

- 目标文件：`<CODEX_HOME 或 ~/.codex>/config.toml` 与 `auth.json`。
- `config.toml`：
  - 选择了模型时设置顶层 `model`；未选择时保持原值。
  - `model_provider = "openai"`。
  - `[model_providers.openai]` 的 `name = profile.name`、`base_url = profile.base_url`、`wire_api` 在 host 为 `api.openai.com` 时为 `"responses"`，否则为 `"chat"`；其他字段原样保留。
  - 已存在 `env_key` 且不是 `OPENAI_API_KEY` → `ENV_KEY_CONFLICT` blocker（否则 `auth.json` 里的密钥可能不生效，不能假装成功）；`env_key = "OPENAI_API_KEY"` 或缺失时允许继续。
- `auth.json`：
  - 档案带密钥时设置 `OPENAI_API_KEY`，保留其他键（包括 OAuth 的 `tokens`、`last_refresh` 等）；存在 OAuth 字段时追加 `OAUTH_AUTH_PRESENT` warning，说明 Codex 可能优先使用登录态，本卡不解析、不修改 OAuth。
  - 档案没有密钥时不改 `auth.json`，返回 `PROFILE_SECRET_EMPTY` warning。
- blockers：TOML / JSON 解析失败、顶层不是表 / 对象、`model_providers` 类型不符、文件无读权限、目标不可写、协议不匹配。
- 重启：`restart_required=true`，文案明确「Codex CLI 需要重启终端或新会话后才会读取新的 config.toml / auth.json」。
- 真实 Codex 版本必须手动确认能读到 `base_url` / `model` / `OPENAI_API_KEY`；若版本行为与上述映射不符，记录实测结果并调整映射，不得只让单测变绿。

### 切换服务与模型（`backend/src/app/services/switch_service.py`、`backend/src/app/schemas/switch.py`）

- 新增 Pydantic 模型，全部 API 输入 / 输出有显式类型，禁止裸 `dict` / `Any`：
  - `SwitchPreviewRequest {tool_id, profile_id, model?}`、`SwitchApplyRequest {tool_id, profile_id, model?, preview_digest, observations}`。
  - `SwitchBlocker {code, message, path?}`，code 至少覆盖 `PROTOCOL_MISMATCH`、`MODEL_UNKNOWN`、`SECRET_MISSING`、`SECRET_STORE_ERROR`、`PARSE_ERROR`、`UNSUPPORTED_VERSION`、`UNSAFE_WRITE`、`PERMISSION_DENIED`、`FILE_NOT_WRITABLE`、`DIRECTORY_NOT_WRITABLE`、`ENV_KEY_CONFLICT`。
  - `SwitchWarning {code, message}`，至少覆盖 `PROFILE_SECRET_EMPTY`、`NO_MODELS`、`MODEL_SHADOWED`、`OAUTH_AUTH_PRESENT`。
  - `SwitchFilePreview {path, format, action(created/updated/unchanged), before_sha256, after_sha256, before_size, after_size, changes}`，不包含文件内容。
  - `SwitchPreviewResponse {tool_id, profile_id, model, available_models, files, blockers, warnings, restart_required, restart_message, observations, preview_digest, can_apply}`。
  - `SwitchApplyResponse {tool_id, profile_id, snapshot_id, audit_id, files, binding, warnings, restart_required, restart_message, applied_at}`。
- 预览算法：
  1. 确认工具存在且已安装；未知 / 未安装 → 404 `TOOL_NOT_FOUND`。
  2. 读取档案；不存在 → 404 `PROFILE_NOT_FOUND`；协议不在 `adapter.supported_protocols` → `PROTOCOL_MISMATCH` blocker。
  3. 解析模型：显式 `model` 必须在档案清单中，否则 422 `SWITCH_MODEL_UNKNOWN`；未指定且有清单 → 第一项；清单为空 → `null` + `NO_MODELS` warning。
  4. 读取密钥：`secret_ref` 存在但取不到 → `SECRET_MISSING` blocker；密钥存储异常 → `SECRET_STORE_ERROR`；`secret_ref` 为空 → `PROFILE_SECRET_EMPTY` warning，不阻塞。
  5. 每个 `managed_paths` 用一次 `read_file_with_bytes` 读取字节 / 观察值 / 权限；无读权限 → blocker；目标已存在但不可写，或父目录不可写 → blocker。**预览不得创建目录、不得写文件。**
  6. 调 `adapter.plan`；对没有 blocker 的文件调 `render` / `verify`，得到 `expected_bytes`；有 blocker 的文件不参与 apply。
  7. `preview_digest = sha256(canonical_json({tool_id, profile_id, profile_updated_at, model, files:[{path, exists, sha256, size, expected_sha256}]}))`；不把 `mtime_ns` 放进 digest（仅 mtime 变化不算冲突）。
  8. `can_apply = not blockers`；返回预览。全程零落盘、零快照、零审计、零绑定变更。
- apply 算法：
  1. 按同样输入重新生成计划；若 `preview_digest` 与请求不一致 → 409 `SWITCH_PREVIEW_STALE`，details 含 `stale_paths`，零写入。
  2. 若仍有 blockers → 409 `SWITCH_BLOCKED`，message 列出原因，零写入。
  3. 请求中的 `observations` 必须与重新观察到的文件路径 / `exists` / `sha256` / `size` 一致；不一致 → `WriteConflict`（409，details 含冲突），零写入。
  4. 用请求携带的 `observations` 构造 `WritePlan`，调用 007 `WriteEngine.apply`；由它完成写锁、最终冲突检查、预快照、原子写、回读、审计。
  5. 写成功后，在 `ProfileRepository.mutate` 内重新读取档案并校验 `updated_at` 与预览时一致；不一致 → 抛 `SWITCH_PREVIEW_STALE`，随后用本次快照回滚文件。一致则 upsert `ToolBinding {tool_id, profile_id, bound_at=原值或 now, active=true, applied_at=now, snapshot_id}`。
  6. 绑定保存失败 → 用 `SnapshotService.rollback(snapshot_id)` 自动还原文件；还原成功返回 `BINDING_WRITE_FAILED`（500，说明「配置已还原，绑定未保存」）；还原失败返回 `APPLY_ROLLBACK_FAILED`（500，含快照 ID 与两边原因）。不得返回成功。
  7. 成功响应必须带 `restart_required` / `restart_message`；写引擎的 `WriteResult` 与绑定视图原样透传，不拼裸 dict。
- 任何路径必须是绝对、规范化、已解析 symlink 的路径；重复路径、相对路径、`..` 直接拒绝。
- 审计：apply 的成功 / 失败 / 冲突由 007 写引擎记录；绑定失败与自动回滚额外记录一条 `apply` / `failed` 审计。审计只含 `path.field`、快照 ID、结果与脱敏消息。
- 测试必须覆盖：正常预览 / 应用、模型默认 / 选择 / 非法、协议不匹配、空模型清单、缺失密钥、密钥存储异常、损坏文件、只读文件、无权限目录、外部改动、过期 digest、绑定写失败回滚、并发 apply、锁超时、审计失败、秘密不泄露。

### API（`backend/src/app/api/switch.py`、`backend/src/app/api/audit.py`、`backend/src/app/core/errors.py`）

- `POST /api/switch/preview` → 200 `SwitchPreviewResponse`；`POST /api/switch/apply` → 200 `SwitchApplyResponse`；同步 `def`，只做参数绑定 / 转发，业务在 service，数据访问在 repository。
- `GET /api/audit?tool_id=<id>&limit=<n>` → 200 `AuditListResponse {entries}`；`limit` 默认 50、范围 1–200；未知工具返回空列表；读取失败 → 500 `AUDIT_UNREADABLE`。
- `ErrorResponse` 增加可选 `details: ErrorDetails | None`，`ErrorDetails {conflicts, stale_paths}`；`WriteConflict` 设置 `details.conflicts`，`SWITCH_PREVIEW_STALE` 设置 `details.stale_paths`。序列化时 `exclude_none=True`，其他错误响应仍是 `{code, message}`，既有测试不得被破坏。
- 错误码：404 `TOOL_NOT_FOUND` / `PROFILE_NOT_FOUND`；409 `SWITCH_BLOCKED` / `SWITCH_PREVIEW_STALE` / `WRITE_CONFLICT`；422 `VALIDATION_ERROR` / `SWITCH_MODEL_UNKNOWN`；500 `WRITE_VERIFY_FAILED` / `WRITE_FAILED` / `WRITE_RESTORE_FAILED` / `AUDIT_WRITE_FAILED` / `BINDING_WRITE_FAILED` / `APPLY_ROLLBACK_FAILED`；503 `WRITE_LOCK_TIMEOUT` / `PROFILE_STORE_LOCK_TIMEOUT`。`api/` 不手写 `HTTPException`。
- 响应绝不包含：文件原文、`expected_bytes`、密钥明文、快照 chunk 内容、可直接下载的快照原文。

### 前端（`frontend/src/`）

- 新增 `api/switch.ts`、`api/snapshots.ts`，所有请求走 `requestJson`，类型显式；组件禁止直接 `fetch`。`ApiError` 增加可选 `details` 解析（冲突路径 / 过期文件），测试覆盖旧响应形状仍可用。
- 主界面 `HomeView` 好友详情内：
  - 「切换档案」区：档案选择、模型选择（档案清单为空时显示「保持当前模型」）、「预览改动」按钮；默认选中当前绑定档案，没有绑定则选中第一份档案。
  - 预览确认框：逐文件路径 + 字段级 before / after 表（`set` / `remove`），blockers / warnings，醒目的重启提示；有 blocker 时确认按钮禁用；取消不发 apply、不改变磁盘。
  - 应用成功：关闭确认框，显示「已应用 + 重启要求 + 快照 ID」；刷新工具详情、档案绑定与快照列表；不得只显示「成功」。
  - 应用失败：保留确认框与用户选择，显示可读错误；`WRITE_CONFLICT` 显示冲突文件 / 原因与「重新预览」入口，不自动合并、不覆盖。
- 「快照 / 回滚」区：列出当前工具的 `created_at`、`reason`、文件、变更摘要、pin 状态；支持 pin / unpin、确认后回滚；回滚成功显示预回滚快照 ID 与恢复文件；空列表显示「暂无快照，应用档案后会自动生成」；列表 warnings 可见。不得提供快照内容下载。
- `/profiles` 的 `BindingPanel` 移除「切换在 008 实现」：显示「已应用 + 时间 / 快照」或「已绑定，尚未应用」；档案 `updated_at` 晚于绑定 `applied_at` 时显示「档案已修改，需重新应用」；不复制切换 UI。
- 所有交互用原生 `button` / `dialog` 语义、`aria-*`、`:focus-visible`；组件测试用 `getByRole` / `getByText`，覆盖加载、空、错误、取消、成功、冲突、重启提示与键盘可达。
- 不新增前端依赖、不改 `pnpm-lock.yaml`。

### 文档与验收

- `README.md`：补充切换预览 / 应用 API、`/api/audit`、逐字段 diff 与重启语义、冲突处理、密钥写入策略与脱敏边界、快照 UI、手动 curl 验收；更新工具能力（write）说明。
- `PROGRESS.md`：开卡决策、实现交接、断言变更理由（capabilities write 与档案页文案）、下一个可执行命令。
- 手动验收（临时 `CLAUDE_CONFIG_DIR` / `CODEX_HOME`，不碰真实用户配置）：
  1. 预览前后目标文件 hash 与快照 / 审计数量不变。
  2. apply 后目标字段符合预期，其余内容逐字符不变；快照、审计、绑定均可追溯。
  3. 外部改动后 apply 被 409 拦下，文件未被覆盖；重新预览后可再次应用。
  4. 只读文件 / 无权限目录被 blocker 或可读错误拦下，零写入。
  5. 取消预览磁盘零变化；重启提示真实可见。
  6. 回滚后文件与 apply 前逐字节一致（`Get-FileHash` / `sha256` / `cmp`）。
  7. 真实 Codex 启动后读到所选 provider / model / key；若版本行为不符，记录并调整映射。
  8. 界面宽度 < 768px、键盘操作、冲突提示与空状态可用。
- `check.py` 退出码 0，完整输出贴进 `tasks.md`。

## 范围

```scope
backend/src/**
backend/tests/**
frontend/src/**
README.md
```

- `backend/src/**`：新增 `app/adapters` 的写契约 helper、`app/schemas/switch.py`、`app/services/switch_service.py`、`app/api/switch.py`、`app/api/audit.py`；在 `app/adapters/base.py` / `claude_code.py` / `codex_cli.py` 增加 `plan` / `render` / `verify` / `supported_protocols` / 写能力；在 `app/core/errors.py` 增加 `ErrorDetails` 与 `details`；在 `app/main.py` 挂载路由；必要时在 `app/schemas/tool.py` / `app/services/tool_discovery.py` 暴露写能力。
- `backend/tests/**`：适配器写契约、Claude / Codex 映射、switch API、apply / 冲突 / 回滚 / 并发 / 脱敏、audit API；复用 `profile_fixtures.py`、`snapshot_fixtures.py`、`tool_fixtures.py`，必要时新增 `switch_fixtures.py`。
- `frontend/src/**`：`api/switch.ts`、`api/snapshots.ts`、`stores/switches.ts`、`stores/snapshots.ts`、`components/SwitchPanel.vue`、`components/SwitchPreviewDialog.vue`、`components/SnapshotPanel.vue`、`views/HomeView.vue`、`components/BindingPanel.vue`、`views/ProfilesView.vue`、`api/client.ts` 与对应测试；可拆分组件，单文件不超过 ~150 行。
- `README.md`：切换 / 快照 / 审计 / 密钥边界 / 手动验收。
- 不改 `backend/pyproject.toml`、`backend/uv.lock`、`frontend/package.json`、`frontend/pnpm-lock.yaml`（本卡不新增依赖）；不改 `docs/**`、`rules/**`、`scripts/**`；不改 004 的 `detect` / `read` 只读语义；不改 006 的档案 CRUD / 密钥后端行为；不改 007 的写引擎 / 快照存储语义。
- `PROGRESS.md`、`specs/**` 由 guard 固定放行；本卡只改本目录、`specs/CURRENT` 与交接记录。

## 边界用例（实现时必须想到）

1. 缺失配置文件：两次 apply 均能创建；父目录不存在时 apply 创建父目录，预览不创建；创建失败可读报错。
2. BOM / CRLF / 无结尾换行 / Unicode / 注释 / 键序 / 未知字段：render 与 apply 后除目标字段外逐字节不变；verify 检测到未知内容被破坏时拒绝。
3. 空档案模型清单：保持工具当前模型，预览显示 `NO_MODELS`，apply 不写模型字段；模型不在清单 → 422。
4. 档案无密钥 / 密钥引用存在但值缺失 / 密钥存储不可用：分别是 warning、blocker、500；不得把缺失伪装成「未设置」。
5. 目标文件损坏 / 非 UTF-8 / 顶层不是对象 / 重复键 / 中间路径类型不符：预览返回 blocker 或 `UNSAFE_WRITE`，零写入。
6. 只读文件、无权限目录、文件被其他进程占用：预览 blocker；apply 零写入或写失败后还原；不得留下半截文件。
7. 外部改动：预览后被改内容 / 删除 / 新建 → apply 409 `WRITE_CONFLICT`，details 含两边 hash；仅 mtime 变化不冲突；文件不被覆盖。
8. 预览后档案被编辑 / 删除、模型变化、密钥变化：digest 或 `updated_at` 不一致 → `SWITCH_PREVIEW_STALE`，零写入。
9. 并发 apply：写锁串行化，最多一个成功；另一个得到 `WRITE_CONFLICT`；快照 / 审计 / 绑定状态一致。
10. 绑定保存失败 / 档案库锁超时 / 审计写失败：自动还原文件；还原失败返回 `APPLY_ROLLBACK_FAILED`；不得假成功。
11. 秘密泄露：fixture 密钥不出现在预览响应、审计表、快照 `meta.json`、错误消息、日志；工具配置文件本身含密钥是预期行为；快照原始 blob 可能含旧密钥但不提供下载。
12. 协议不匹配、`env_key` 冲突、OAuth 登录态、`MODEL_SHADOWED`：blocker 或 warning 文案可读，不能静默继续。
13. 快照列表空 / 损坏 / pin / unpin / 回滚：损坏项跳过并 warning；pin 幂等；回滚前自动快照；回滚后逐字节一致。
14. 前端：取消、双击、慢请求、超时、409、409 details、重启提示、空状态、窄屏、键盘 focus；不得出现假成功或只显示「成功」。
15. Windows：路径解析、文件锁、`os.replace`、权限分支可运行；Unix 权限断言只在 POSIX 执行。

## 不做（明确划界）

- 不做全局只读模式与统一写端点拦截（016）；不做审计 UI / 筛选（016）；不做健康体检（009）、新工具适配（020）、启动器 / 会话 / 应用内对话。
- 不做自动合并、后台自动同步、云端同步；冲突只拒绝并展示，重新预览由用户显式触发。
- 不提供快照内容下载、导出、加密、压缩；不把快照元数据放进 SQLite。
- 不改 004 的 `detect` / `read` 行为、006 的档案 / 绑定 / 密钥语义、007 的写引擎 / 快照存储语义；不改 `GET /api/tools` 的只读字段，除本卡明确变更的 `capabilities.write` / `write_mode`。
- 不新增后端 / 前端依赖；不改 lock 文件；不做 `app/adapters` 之外的动态插件加载。
- 不在本卡解析 / 修改 OAuth 凭据；不在用户未确认时写任何工具配置。