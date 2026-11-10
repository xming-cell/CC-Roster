# 005 — 微信式主界面骨架

> 输入：`docs/task-plan.md` 的 005 卡；`docs/requirements.md` F-06 / N-9 / N-10；`docs/decisions.md` ADR-002；`specs/004-tool-discovery/spec.md` 与现有 `GET /api/tools`。
> 依赖：004 已完成（工具发现、状态推导、`GET /api/tools`、前端 store 与请求层可用）。
> 本卡只做前端主界面骨架，不新增后端能力，不写任何工具文件。

## 开卡决策（2026-11-09，用户确认）

1. **主界面挂在 `/`**：重写 `HomeView.vue` 为微信式左右结构；`/tools` 保留现有 `ToolsView` 作为过渡入口，不删除、不改其断言。`/` 不再展示 health 文案；`GET /api/health` 与 `stores/app.ts` 保留，供后续卡使用。
2. **「最近使用」先用 `last_modified` 代理**：按 004 返回的 `last_modified` 降序；`null` 或无法解析的时间排最后；相同时间按 `display_name`、`id` 升序稳定排序。真正的使用时间等 012 / 013 有会话与启动数据后再替换，本卡不新增持久化。
3. **只改前端**：复用 `stores/tools.ts` 与 `/api/tools`，不改 `backend/**`，不新增依赖。`App.spec.ts` 中两条关于 `/` 的 health 断言随首页行为变更更新（不是为让测试变绿），理由同步写入 `PROGRESS.md`（AGENTS.md 第 4 条）。

## 背景与目标

1. 004 已经能发现工具、读取配置并在 `/tools` 展示最小列表；005 把 `/` 变成用户打开即见的微信式主界面，落地 F-06 的 P0 体验。
2. 好友 = 一个已安装工具（ADR-002），当前档案只是好友属性；本卡只做「谁在这里、状态如何、选中后看详情」的骨架，不实现聊天、搜索、体检与外观。
3. 复用 004 的数据与脱敏结果，不新增接口；为 010（搜索）、011（独立外观）、012 / 014（会话）预留位置与主题覆盖点。

目标（按优先级）：

1. 左列表右详情、四态徽章、一行状态描述、稳定排序。
2. 空状态与「怎么装」引导、部分失败 warnings、loading / 错误态诚实可见。
3. 扫描不阻塞首屏；键盘可达、窄窗口不横向滚动。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。
- 布局与视觉 token：
  - 新增全局样式 token（如 `frontend/src/styles/tokens.css`，由 `main.ts` 引入），至少覆盖颜色、字号、间距、圆角、头像与气泡；提供 `--friend-accent`、`--friend-avatar-bg`、`--bubble-*` 等可覆盖变量，F-09 后续可按好友覆盖而不改组件结构。
  - `/` 为占满视口高度的左右结构：左好友栏 + 右详情 / 会话区；右侧未选中时显示空状态；页面无横向滚动。
  - 视觉接近即时通讯：列表行分隔、头像 + 名称 + 一行描述 + 状态徽章；不是仪表盘式卡片堆叠。
- 左侧好友列表：
  - 条目含头像位（无图片时用名称首字 / 工具缩写，背景由工具 ID 稳定推导）、名称、一行状态描述、四态徽章（正常 / 未配置 / 异常 / 检测中）。
  - 状态描述：`ok` → 供应商 / 模型（缺失时「已配置」）；`unconfigured` → 「已安装，尚未配置」；`error` → 首条 warning 的 message（无则「配置解析失败」）；loading → 「正在检测…」。不得出现假成功。
  - 排序：`last_modified` 降序；`null` / 非法时间排最后；同值按 `display_name`、`id` 升序；`:key="tool.id"`。
  - 选中态明确（`aria-pressed` 或等价），点击更新右侧；刷新后按 ID 保持选中，条目消失时回到未选中空状态。
- 右侧详情 / 会话区：
  - 顶部显示当前好友名称与状态徽章；复用 `ToolDetailPanel`（或等价组件）展示 004 已有字段：状态、供应商、模型、接口地址、第三方中转、脱敏密钥、最后修改时间、配置路径、warnings。
  - 未选中时显示「选择一个 AI 查看详情」空状态；为 012 / 014 的会话时间线预留容器，但本卡不渲染会话内容。
- 空状态、warnings 与错误：
  - 全部工具为空：显示「还没有发现任何 AI 工具」+「怎么装」入口；入口展开后给出 Claude Code / Codex CLI 的最小安装 / 配置指引（纯文本，不发网络请求）。
  - 部分失败：其他好友正常展示；全局 warnings 可见（可折叠，但默认有可发现入口）；单条 warning 同时在详情中可见。
  - 初始请求失败：主界面骨架仍在，列表区显示可读错误与「重试」；重试成功后恢复。
  - 刷新失败：保留旧列表并显示非阻塞提示，不清空成假成功。
  - loading：列表显示骨架 / 「检测中」徽章；主界面骨架先渲染，扫描不阻塞首屏（N-9）。
- 可访问性与响应式：
  - 列表使用语义化 `ul` + `button`（或等价），有 `aria-label`；Tab 可达，Enter / Space 选中，`:focus-visible` 可见；选中态用 `aria-pressed` / `aria-current` 表达。
  - 头像为装饰性 `aria-hidden`，名称文本可读；正文对比度满足 WCAG AA（≥ 4.5:1）。
  - 窄窗口（< 768px）单列：列表在上、详情在下或抽屉，无横向滚动；320px 宽仍可用。
- 测试与代码约束：
  - Vitest 覆盖：列表渲染与排序（含 `last_modified` 为 null / 相同值）、四态徽章、选中 / 详情、空状态 + 安装引导、部分失败 warnings、初始失败 + 重试、刷新失败保留旧列表、加载时骨架先渲染（deferred promise）。
  - 断言用 `getByRole` / `getByText`（沿用 `__tests__/dom.ts`）；不新增测试依赖；无 `.skip` / `.only`、无 `any` / `@ts-ignore`。
  - 组件不直接 `fetch`，只经 store / `api/tools.ts`；无新依赖。
- 文档：
  - `README.md` 更新 `/` 主界面与 `/tools` 过渡入口说明；`PROGRESS.md` 记录开卡与 App.spec 断言变更理由。
  - 不改 `backend/**`、`docs/**`、`rules/**`、`scripts/**`、`frontend/package.json` / `pnpm-lock.yaml`、`frontend/vite.config.ts` / `vitest.config.ts` / `eslint.config.ts`。

## 范围

```scope
frontend/src/**
README.md
```

- `frontend/src/**`：重写 `views/HomeView.vue`；新增好友列表 / 空状态 / 骨架等组件与 `styles/tokens.css`；按需调整 `App.vue` 布局与 `stores/tools.ts` 的选中 / 刷新语义；新增 / 更新 Vitest。`/tools` 与 `ToolsView.vue` 保持现状。
- `README.md`：主界面入口、`/tools` 过渡入口与本地查看方式。
- `PROGRESS.md`、`specs/**` 由 guard 固定放行；本卡只改本目录、`specs/CURRENT` 与交接记录。
- 不改 `backend/**`、`docs/**`、`rules/**`、`scripts/**`、`frontend/package.json` / `pnpm-lock.yaml`、`frontend/vite.config.ts` / `vitest.config.ts` / `eslint.config.ts`；不改 004 的后端断言与 `ToolsView.spec.ts`。

## 边界用例（实现时必须想到）

1. 一个工具都没安装：`/` 显示空状态与「怎么装」，不报错、不出现假列表。
2. `last_modified` 为 `null`、非法日期字符串或多个工具时间相同：排序稳定且可预测（null / 非法排最后，同值按 `display_name`、`id`）。
3. 名称、供应商、模型或 warning 很长：列表只显示一行并截断，不撑破布局；完整内容可在详情或 `title` 中获取。
4. 首屏加载：接口未返回前主界面骨架已可见；用 deferred promise 断言，不允许整页空白或阻塞渲染。
5. 连续刷新 / 快速双击：按钮防重复或采用 latest-wins，旧响应不得覆盖新结果。
6. 初始请求失败：错误可读、可重试；重试成功后列表与选中态正常。
7. 刷新失败但已有数据：保留旧列表并给非阻塞提示，不清空、不显示成功。
8. 部分失败：某个工具 `error` 时其他好友仍展示；全局 warning 与详情 warning 都能看到。
9. 选中的好友在刷新后消失：回到未选中空状态，不保留悬空详情或抛错。
10. 后端未来返回未知 `status`：前端降级为「异常」或等价兜底，不崩溃、不误报正常。
11. 键盘操作：Tab 能到达列表项，Enter / Space 可选中，focus 可见；空状态里的「怎么装」也能用键盘展开 / 收起。
12. 窄窗口（320px / 600px）：单列布局、无横向滚动，详情仍可到达；头像与徽章不重叠。
13. 工具数量较多（如 100 条）：排序与渲染为轻量同步操作，首屏 1 秒内可见；本卡不做虚拟滚动。
14. 深链接：直接打开 `/` 进入主界面；`/tools` 仍按 004 的行为渲染，不受本卡影响。

## 不做（明确划界）

- 不实现搜索 / 筛选（010）、每个 AI 独立外观覆盖（011）、会话历史回放（012）、应用内对话（014）、健康体检 UI（009）、启动器（013）、桌面壳（015）。
- 不新增或修改后端 API、领域模型、SQLite 表或工具文件；不新增第三方依赖。
- 不删除、重构或改断言 `ToolsView.vue` / `ToolsView.spec.ts`；不改 `/tools` 路由行为。
- 不做移动端专门适配（只保证窄窗口桌面可用）、不做完整主题切换 / 暗色模式（011）。
- 不做虚拟滚动、图表、仪表盘式首页。
- 不改 `requirements.md` 的边界与「明确不做」事项。