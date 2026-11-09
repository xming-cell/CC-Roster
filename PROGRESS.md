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

## 下一个可执行命令

```bash
# 1) 任何时候先跑这个，退出码 0 才算"完成"
uv run python scripts/check.py
```

开新任务时的固定动作：

1. 复制 `specs/_template/` → `specs/NNN-<短名>/`，填 `spec.md` 的 DoD 与 scope 块；
2. 把 `specs/CURRENT` 改成 `NNN`（不改则 `guard scope` 会跳过范围校验）；
3. 只动 scope 内的文件，做完把 check.py 输出贴进 `tasks.md`。

卡片状态：`specs/003-local-infra`、`specs/004-tool-discovery`（004 — 工具发现与只读配置，T1–T8）均已完成；`specs/CURRENT` 暂时仍指向 004。开新卡时按上面的固定动作建目录、改 `specs/CURRENT`，再按新卡 `tasks.md` 顺序推进。

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