# 039 — 本机供应商配置导入覆盖全部工具并确保落库可见

> 来源：用户 2026-11-18 反馈（对应规划 113）。
> 依赖：105（JSON 导入）、110（TOML / Codex 配置读取）、102（绑定模型）已完成。
> 性质：既有导入功能的缺陷修复 + 本机配置读取范围扩展；不是新供应商体系。

## 背景与目标

1. 导入弹窗目前只有「从 Codex 配置读取」一个本机来源；Claude Code、Gemini CLI、OpenCode 的适配器虽然能读取各自配置，但导入界面无法选择。
2. Codex 本机配置显示「导入成功」后，供应商页仍为空。已定位原因：导入只写入全局 `Profile`，没有创建 `ToolBinding`；供应商页按选中工具的绑定过滤，因此未绑定的导入项不可见。
3. 目标 1：只要本机存在可读配置，Claude / Codex / Gemini / OpenCode 都能从导入弹窗读取并预览。
4. 目标 2：导入成功后，新增 / 覆盖的供应商立即出现在供应商页，且保持「未启用」；不自动激活、不写工具配置。
5. 目标 3：导入结果与成功提示必须反映「实际落到了哪里」，不能出现“显示成功但列表为空”。

## 已定位的实现事实（供实现时核对）

- `frontend/src/components/ImportProvidersDialog.vue`：来源类型硬编码为 `'file' | 'codex'`，只调用 Codex 专用 API。
- `backend/src/app/services/profile_import_service.py`：只有 `preview_codex()` / `import_codex()`；`_import_parsed()` 只创建 `Profile`，没有创建 `ToolBinding`。
- `backend/src/app/services/profile_service.py`：`list_profiles(tool_id)` 先按 `tool_id` 过滤绑定，再只返回已绑定档案。
- `frontend/src/views/ProvidersView.vue`：`handleImported()` 会刷新页面，但刷新后仍只显示已绑定档案，所以导入结果不可见。
- 已确认：以 105 的 DoD 为准。本机配置导入绑定到「来源工具」（Claude 配置 → Claude Code，Codex 配置 → Codex CLI，以此类推）；文件导入绑定到当前选中的工具；导入后自动切到对应工具，列表立即可见，状态 `active=false`。`docs/design/06-acceptance.md` 的 I-6 随后同步改为「可见且已绑定、未启用」。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- 导入弹窗提供「从本机配置读取」的工具选择，至少覆盖 Claude Code / Codex CLI / Gemini CLI / OpenCode；未安装或配置不可读时显示禁用状态和可读原因，不隐藏成“只有 Codex”。
- 后端提供按 `tool_id` 的通用本机配置预览 / 导入端点（或等价设计），不再把 Codex 写死在 API 路径与 service 方法里。
- 各工具映射至少覆盖：
  - Claude Code：`settings.json` 的 `env.ANTHROPIC_BASE_URL`、`env.ANTHROPIC_AUTH_TOKEN` / `env.ANTHROPIC_API_KEY`、`env.ANTHROPIC_MODEL` / 顶层 `model`。
  - Codex CLI：现有 `model_providers.<id>`、`base_url`、`wire_api`、`experimental_bearer_token` / `env_key` 行为保持不变。
  - Gemini CLI：`settings.json` 的 `baseUrl` / `model`；环境变量里的密钥不读取，标「无密钥」。
  - OpenCode：`opencode.json` 的 `provider.openai.options.baseURL` / `model`；环境变量里的密钥不读取，标「无密钥」。
- 导入成功后，供应商页自动切到对应工具，并立即可见本次新增 / 覆盖的供应商；必须是用户可观察到的列表项，不能只弹成功提示。
- 本机配置导入绑定到来源工具；JSON / TOML 文件导入绑定到当前选中的工具；两种入口都保持 `active=false`，不自动激活。
- 导入后的供应商一律不自动激活，不写回任何工具配置文件；成功提示说明「已加入 / 已更新，未启用」。
- 预览、错误、审计、日志均不回显 token / bearer / API key 明文。
- 空配置、配置不存在、JSON / TOML 解析失败、没有可导入字段、重复项、超长、未知协议都有可读错误。
- 测试覆盖：四个工具的预览与导入、配置文件缺失 / 损坏、无可导入字段、重复策略、导入后列表可见、重复提交幂等、跨工具隔离、密钥不泄漏、原配置文件 hash 不变。
- 设计稿更新并经用户确认：导入弹窗的工具来源列表、各工具预览、导入成功后的供应商列表。

## 范围

```scope
backend/src/**
backend/tests/**
frontend/src/**
docs/design/**
docs/task-board.md
docs/decisions.md
```

## 边界用例（实现时必须想到）

1. Claude 只使用 OAuth 登录、`settings.json` 没有 base URL / model / token → 给出「没有可导入的供应商字段」；仅有 model 时可使用官方默认地址导入，标「无密钥」。
2. Gemini / OpenCode 只有环境变量里的 API key → 不读取进程环境变量，导入无密钥档案并提示用户到供应商页补充。
3. Claude `env.ANTHROPIC_AUTH_TOKEN` 与 `ANTHROPIC_API_KEY` 同时存在 → 只取一个，预览只显示「有密钥」，不显示值。
4. Codex 配置有多个 provider、只有 `env_key`、未知 `wire_api` → 分别按候选、无密钥、非法处理；不部分写入。
5. 同一配置重复导入 → 按「名称 + 协议 + 地址」去重；skip / overwrite 行为确定，不产生重复绑定。
6. 当前选中的工具与导入来源工具不同 → 绑定到来源工具，导入成功后自动切到该工具；不得出现“导入了但当前列表看不到”。
7. 工具未安装但本机有残留配置 → 允许读取与导入，并在预览中标「工具未安装」；不因未安装而隐藏配置。
8. 配置文件 hash 在读取 / 预览 / 导入前后不变；本应用只读外部配置。

## 已确认决策（2026-11-18）

1. **导入落点**：采用方案 A。本机配置导入绑定到来源工具；JSON / TOML 文件导入绑定到当前选中的工具；导入后自动切到对应工具，列表立即可见，状态 `active=false`。不做单独的「未绑定」区。
2. **读取范围**：只读取配置文件里明确写出的非 OAuth 字段（Claude `settings.json`、Gemini `settings.json`、OpenCode `opencode.json`、Codex `config.toml`），不读取进程环境变量和 OAuth 凭据。
3. **工具范围**：覆盖现有 4 个适配器（Claude Code / Codex CLI / Gemini CLI / OpenCode）；Cursor 暂不做。
4. **Claude 无 base URL**：使用 Anthropic 官方默认地址 `https://api.anthropic.com` 生成候选，并在预览里标注「来自默认值」。

## 不做（明确划界）

- 不读取 OAuth token、系统钥匙串、进程环境变量里的密钥。
- 不把本应用内部 `profiles.json` 改成 TOML。
- 不反向写回 `~/.codex/config.toml`、`~/.claude/settings.json`、Gemini / OpenCode 配置。
- 不导入 `mcp_servers`、plugins、projects、会话、用量等非供应商数据。
- 不做 CSV / YAML / 远程 URL 导入。
- 不自动激活导入的供应商。