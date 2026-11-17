# 进度

## 当前状态

- 骨架完成：后端 health 端点 + 1 个测试；前端调通 `/api/health`；`scripts/check.py` 七道门 + CI 打通。
- 工作流基线加固完成（任务卡 001）：规则已机器化，`check.py` 现在含 `guard scope` / `guard forbidden` 两步硬门禁。
- 根目录 `README.md` 已改写为「产品介绍 + 开发者上手」文档；该文件已在 001 卡 scope 中登记（同卡文档改动）。
- 已产出后续任务拆解初稿 `docs/task-plan.md`：覆盖 F-01～F-17 / N-1～N-11。
- 任务卡 002 完成：D-1～D-8 已拍板并写入 `docs/decisions.md`；适配器契约与领域模型成文；未写业务代码。
- 任务卡 003 完成（`specs/003-local-infra`，本地应用基础设施）：统一错误模型、带时区时钟与跨平台数据目录、SQLite bootstrap（WAL / `user_version` 幂等迁移）、原子 JSON 写与跨平台文件锁、请求体上限与 CORS 白名单、结构化日志与 ADR-006 三档脱敏、前端请求层 / 路由 / Pinia / 应用壳；README 已补数据目录、loopback、日志与启动说明。
- 任务卡 004 已开工（`specs/004-tool-discovery`，工具发现与只读配置）：T1–T7 完成——`ToolAdapter` 协议、`build_registry()` 显式注册表、可注入 `environ` / `home` / `which`，共享只读契约骨架（空目录 / 未知结构 / 权限不足 / 重复调用 / 读取前后目录 hash 不变）；Claude Code 适配器（`settings.json`，`CLAUDE_CONFIG_DIR` / `~/.claude`，不读 OAuth）与 Codex CLI 适配器（`config.toml` + `auth.json`，`CODEX_HOME` / `~/.codex`，`env_key` 只提示不读取）已注册，fixture 覆盖损坏 / 空文件 / 未知结构 / 权限不足 / provider 缺失 / 未知 `wire_api`；T4 收敛 warning code 为 `WarningCode` 字面量契约，新增 `ToolDiscoveryService`（`app/services/tool_discovery.py`）聚合并隔离单适配器异常，`app/schemas/tool.py` 定义 `ToolView` / `ToolListResponse`，状态推导为 ok / unconfigured / error；T5 在 `ToolWarning` 构造边界统一 `redact_text`，新增 `test_tool_secrets.py` 断言列表 / 详情 / 损坏文件 / warning / 日志完整序列化均无明文 key；T6 新增同步 `def` 端点 `GET /api/tools` / `GET /api/tools/{tool_id}`（`app/api/tools.py`），`Depends(get_tool_service)` 按请求构造服务，`test_tools_api.py` 覆盖正常 / 空列表 / 部分失败 / 未知 ID / 未安装 / 连续调用与文件只读；T7 新增 `api/tools.ts`、`stores/tools.ts`、`/tools` 路由与「工具」入口、`ToolsView` + 状态徽章 / 详情面板，Vitest 覆盖列表 / 详情 / 空态 / 加载态 / 失败态 / 部分失败。开卡决策：扫描结果不落 SQLite；前端新增 `/tools` 路由；不执行 CLI `--version`（`version` 恒为 `null`）。003 注释里「索引 / 缓存表由 004 追加」的默认预期顺延到确有性能需要的卡。T8 完成：手动验收表已填写；README 补充 `/api/tools`、`/tools` 页面与 `CLAUDE_CONFIG_DIR` / `CODEX_HOME` 本地验收方式；`check.py` 全绿并记录到 `specs/004-tool-discovery/tasks.md`。
- 换行符统一（已做，scope 已登记）：仓库根新增 `.gitattributes` 声明 `* text=auto eol=lf`。原因：Windows 侧 git（`core.autocrlf=true`）把工作区 checkout 成 CRLF，WSL / Linux / CI 的 git 默认不做转换，`scripts/guards.py` 用 `git diff --name-only HEAD` 取改动清单时把每个 CRLF 文件当成"已修改"，实测在 WSL 里误报 12 个从未动过的文件越界。同批改动里顺手删除了仓库根误建的 0 字节文件 `; done`（命令里的 `; done` 被 shell 当成重定向目标写出来，单独就能让 `guard scope` 失败）。
- 最近一次验收：见 `specs/004-tool-discovery/tasks.md` 的「验收记录」（`check.py` 全绿）。
- 任务卡 005a（前端信息架构基线）与 023（跨平台 CI 对齐）已完成并记录验收；`specs/CURRENT` 已从 023 切到 024。
- 任务卡 024（V2 任务计划重排）产出 `docs/task-plan2.md`：按新 IA 重排剩余工作，区分前端重建、后端增量与待拍板决策；本卡只改文档，不动业务代码。D-9～D-17 仍待用户确认，确认前不进入 102 及后续实现。
- 任务卡 025（CI 测试隔离）完成：新增 `backend/tests/conftest.py` autouse fixture，把 `LOCALAPPDATA` / `XDG_DATA_HOME` / `HOME` 统一指向每个测试的临时目录；`test_settings_api.py` 改用 `resolve_data_dir()` 推导 settings 路径。修复 macOS CI 上 settings 的 `read_only=true` 泄漏到快照测试的问题；本地 `check.py` 全绿，三平台 CI（ubuntu-latest / macos-latest / windows-latest）已通过（run 43699039463）。
- 任务卡 026（V2 决策与设计基线）已创建：对应 `docs/task-plan2.md` 的 100 号规划卡，含 `spec.md`（DoD / scope / 边界 / 不做）与 `tasks.md`（D-9～D-17 确认清单、tokens / components / acceptance 任务与验收记录）。`specs/CURRENT` 指向 026；决策已完成，见下条。

- 026 设计产物完成（T3/T4/T5 及新增 T3b/T3c）：`docs/design/04-tokens.md` 定稿颜色/字号/间距/圆角/阴影/动效/状态色与「首版只做亮色、令牌层支持双套」策略；`05-components.md` 登记 14 个组件、规格、状态矩阵与可访问性要求；`06-acceptance.md` 给出 A–G 七组可勾选验收项；新增 `07-design-source.md` 明确「Penpot 视觉 / Git 契约」的事实来源划分与「导出代码只作标尺」；`03-hifi/` 建立快照命名与导出规范。D-9～D-17 仍未决，T1/T2 保持待确认。
- 2026-11-16 术语与画板调整（026 / T3d）：按用户决定，主导航「档案」统一改为「供应商」（对应 D-17 方向：后端仍叫 Profile，UI 用供应商）；同步修改 docs/design/01-ia.md 的对象表、导航树、§4.3 与相关流程描述，04-tokens.md、05-components.md（删除 SearchField 组件）、06-acceptance.md（删除搜索相关验收项）一并更新；Penpot 两个画板同批修改，并移除列表面板中的搜索框。IA 变更原因记录于此，符合 026「改动 IA 需单独说明」的约束。
- 待补：`docs/design/03-hifi/` 的实际 PNG 快照（需在 Penpot 界面导出 2x，见该目录 README）。
- 026 完成产品确认（T1/T2/T6）：D-9～D-17 按推荐方案定稿并写入 `docs/decisions.md` 的 ADR-009～ADR-014；界面与文档术语统一为「供应商」（后端 `Profile` 不改名，见 ADR-009）；工具列表搜索框不纳入 V2（ADR-014），Penpot 与 `05/06` 已同步移除；`docs/task-plan2.md` 升 v0.2；`docs/design/03-hifi/` 收入 3 张 2x 快照（工作台默认 / 侧边收起 / 组件总览）。
- 任务卡 027（前端应用壳与工作台工具列表）已创建：对应 `docs/task-plan2.md` 的 101 号规划卡；`spec.md` 已填 DoD、scope、边界与不做，`tasks.md` 已列 T1–T8 与手动验收表；`specs/CURRENT` 已切到 027。本卡只动 `frontend/src/**` 与 `frontend/index.html`，不新增后端接口。

- 2026-11-17 任务卡 027 / `specs/101-workbench-shell` T1–T7 完成：应用壳改为「主导航 + 工具列表 + 工具详情」三栏工作台，`/` 为默认入口、`/tools` 重定向到 `/`，导航仅保留「工作台」。新增全局 tokens / base 样式、品牌区、刷新中保留旧列表、空 / 整体失败 / 部分失败 / 未选中 / 详情加载与错误状态；详情覆盖安装与配置状态、供应商、模型、接口地址、脱敏密钥、配置路径、最后修改时间、版本与 warnings。`stores/tools.ts` 增加 `loaded` 与请求序号，迟到详情响应不会覆盖新选择，同工具重复点击不重复请求，详情错误在切换工具时清除。组件测试 23 项全绿；`uv run python scripts/check.py` 退出码 0。T8 手动验收待做。同步修复 `PROGRESS.md` 中 3 个误写为 NUL 的字符（`04/05/06-*.md` 文件名）与 `specs/CURRENT` 指向（027 → 101 目录前缀）。
- 2026-11-17 027 T1–T7 已提交：`0e9fb43`；026 → 100 目录编号对齐提交：`ceec53c`。028 卡（目录 `specs/102-multi-provider-bindings`，对应 `docs/task-plan2.md` 的 102 号规划卡）已开卡，T1–T7 已完成，`specs/CURRENT` 现指向 102。
- 2026-11-17 028 / `specs/102-multi-provider-bindings` T1–T7 完成：`ProfileStore` 放宽为一工具多绑定（`(tool_id, profile_id)` 唯一、每工具至多一条 active），`ProfileRepository` 增加按工具查询与 `PROFILE_STORE_INVALID` 可读写入错误；`PUT /api/tools/{tool_id}/profile` 只新增绑定，新增 `DELETE /api/tools/{tool_id}/profiles/{profile_id}` 精确解绑，旧 `DELETE .../profile` 改为必须带 `profile_id` 查询参数；`SwitchService._save_binding` 只切换目标 binding 的 active，保留 `bound_at` 与其他绑定；`GET /api/profiles?tool_id=` 支持按工具过滤。新增 23 个多绑定测试，后端 663 passed；T7 手动验收已用 TestClient 跑完并回填 `tasks.md`。`uv run python scripts/check.py` 退出码 0。
- 断言变更说明（规则 4）：`test_profile_bindings.py::test_rebinding_tool_to_another_profile_replaces_old_binding` 改为 `test_binding_second_profile_keeps_first_binding`，原断言固化「绑定 B 会替换 A」的单绑定旧语义，与 ADR-010 / 028 DoD「新增绑定不删除旧绑定」直接冲突；`test_profiles_repository.py::test_mutate_rejects_store_invariant_breach_without_writing` 由期望裸 `ValidationError` 改为期望 `PROFILE_STORE_INVALID` 的 `AppError`，依据 028 DoD「读取 / 写入校验均拒绝，报可读的档案库错误」。
- 2026-11-17 029 / `specs/103-provider-page` 完成（对应 `docs/task-plan2.md` 的 103 号规划卡）：正式编号 029，依赖 101 T1–T7 与 028；只动 `frontend/src/**`。新增 `api/profiles.ts`、`stores/profiles.ts`、`ProvidersView` 与工具列表 / 供应商卡 / 表单 / 删除确认 / 模态壳等组件；`/providers` 路由与主导航「供应商」入口接通。覆盖两栏「工具 → 该工具供应商」、全量摘要与按 `tool_id` 过滤、active / 未启用、创建后绑定 `active=false`、编辑密钥留空保持 / 显式清除、复制、精确解绑、删除 409 占用工具二次确认、健康检查 loading / 结果 / 切换清除、空 / 加载 / 错误 / 密钥降级状态与 Esc 焦点回归。新增 12 个 `ProvidersView` 组件测试并更新 `App` 路由导航测试；`uv run python scripts/check.py` 全绿（663 backend passed / 36 frontend passed）。切换 / 应用 / 写工具配置仍留给 104。
- 2026-11-17 103 已提交（551eed2）。同日建立 docs/task-board.md 作为 V2 进度与设计确认的唯一入口（卡 024b），并把 104–109 建成任务卡；前端开工前必须在 Penpot 出稿并由用户逐卡确认（用户 2026-11-17 约定）。

## 下一个可执行命令

```bash
# 1) 任何时候先跑这个，退出码 0 才算"完成"
uv run python scripts/check.py
```

开新任务时的固定动作：

1. 复制 `specs/_template/` → `specs/NNN-<短名>/`，填 `spec.md` 的 DoD 与 scope 块；
2. 把 `specs/CURRENT` 改成 `NNN`（不改则 `guard scope` 会跳过范围校验）；
3. 只动 scope 内的文件，做完把 check.py 输出贴进 `tasks.md`。

卡片状态：`specs/003-local-infra`、`specs/004-tool-discovery`、`specs/005a-frontend-design`、`specs/023-ci-parity`、`specs/024-replan-v2`、`specs/025-ci-test-isolation`、`specs/100-v2-decision-baseline` 均已完成；`specs/101-workbench-shell`（正式编号 027，对应 `docs/task-plan2.md` 的 101 号规划卡）T1–T7 已提交、T8 手动验收待做；`specs/102-multi-provider-bindings`（正式编号 028，对应 102 号规划卡）T1–T7 已完成并提交；`specs/103-provider-page`（正式编号 029，对应 103 号规划卡）T1–T8 已完成并提交（`551eed2`）。104–109 已建卡；`specs/CURRENT` 现指向 104。进度以 `docs/task-board.md` 为准。开工时按 `specs/<CURRENT>/tasks.md` 顺序推进，完成后更新 `tasks.md`、`docs/task-board.md` 与 `PROGRESS.md`。

## 已知坑

- `AGENT.md`（单数）不是标准文件名，Claude Code / Codex / Gemini CLI 默认只找 `AGENTS.md`——改名后才自动生效。
- Windows 上 `pnpm` 是 `.cmd`，`subprocess` 必须经 shell 启动，否则 `FileNotFoundError`（见 `scripts/check.py` 的 `run()`）。
- `vitest` 不加 `--run` 会进 watch 模式把终端卡死；CI 里要写成 `pnpm run test:unit -- --run`。
- `ruff format --check` 与 `ruff check` 是两道独立门，格式过了不代表 lint 过。
- Windows 控制台代码页是 936，Python 直接 `print` 中文源码片段会 `UnicodeEncodeError`；`scripts/guards.py` 已统一 UTF-8 输出、按 `utf-8-sig` 读文件（BOM 一起吃掉），新脚本照这个抄。
- CRLF 会让 `guard scope` 误报越界：Windows 侧 git 是 `core.autocrlf=true`（工作区 CRLF、仓库 LF），WSL / Linux 侧默认不转换，同一份工作区在两边判定不同。已由仓库根 `.gitattributes`（`* text=auto eol=lf`）固定；若仍在某台机器上看到成片 `M`（内容其实没变，是索引里的 stat 缓存过期），跑 `git read-tree HEAD` 重建索引即可。
- 本机 `github.com` / `raw.githubusercontent.com` 被解析到 127.0.0.1 无法访问；取文件走 jsDelivr 镜像（`gcore.jsdelivr.net/gh/{owner}/{repo}@{branch}/{path}`），列目录走 `data.jsdelivr.com`。`web_search` 也会超时。

## 未决问题

- D-9～D-17 已定稿（ADR-009～014），不再阻塞后续实现卡；101 号规划卡已落为正式卡 027（目录 `specs/101-workbench-shell`），T1–T7 已提交（`0e9fb43`），T8 手动验收仍待做。028 卡（目录 `specs/102-multi-provider-bindings`，对应 102 号规划卡）T1–T7 已完成并提交，`tasks.md` 与手动验收表已回填；103 卡（目录 `specs/103-provider-page`，正式编号 029）T1–T8 已完成并回填。103 的关键边界：只做供应商页与绑定关系，不做切换 / 应用 / 写工具配置（104）；下一步可开 104 卡。
- 前端 e2e（Playwright）尚未接入 `check.py`。`docs/design/03-hifi/` 还缺 103 与 104 的 PNG 快照：Penpot 插件沙箱不允许把导出字节写回本地，当前会话的浏览器控制也被 URL 校验拦住；需在下一次能控制 Penpot 标签页时补导，或由用户手动导出 `04-providers-1440.png`、`05-switch-preview-1440.png`、`06-switch-result-1440.png`、`07-switch-conflict-1440.png`。
- 后端还没有 `repositories/` 层；数据库迁移机制已在 003 就绪，但尚无业务表迁移，`rules/backend.md` 里的数据访问约定暂时无代码可对照。
- `guard forbidden` 目前不拦"注释掉的断言"，这个规则仍靠人看 diff。













