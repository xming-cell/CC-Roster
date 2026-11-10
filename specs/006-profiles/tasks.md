# 006 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [ ] T1 领域模型与 `profiles.json` 仓储：`Profile` / `SecretRef` / `ModelEntry` / `ToolBinding`；根结构 `{schema_version, profiles, bindings}`；缺失文件视为空库，损坏 / 未知版本返回可读错误且不覆盖；复用 `write_json_atomic` + `FileLock`，写操作在锁内「重新读取 → 变更 → 原子写」；读取不落盘、连续调用幂等；测试覆盖空库、损坏、未知版本、并发、锁超时、删除 SQLite 后仍可读。
- [ ] T2 SecretStore 与 keyring 依赖：`SecretStore` 边界（status / get / put / delete）；keyring 优先、`secrets.json` 0600 回退、`CC_ROSTER_SECRET_BACKEND=auto|keyring|file`；响应只露 `has_secret` / `secret_preview` / `secret_backend`；两步写入补偿；`keyring` 写入 `pyproject.toml` 与 `uv.lock` 并写明理由；测试注入假 keyring，覆盖回退、缺失、读写失败、完整序列化无明文。
- [ ] T3 档案 CRUD API：`GET /api/profiles`、`POST`（201）、`GET /{id}`、`PATCH`、`POST /{id}/copy`、`DELETE ?confirm=true`；名称 / URL / 协议 / 模型校验；重名、空名称、非法 URL、未知字段、404 / 409 / 500 错误码；复制密钥与名称自动后缀；测试走 `TestClient`，并断言工具配置文件 hash 不变。
- [ ] T4 模型清单编辑：`ModelEntry {id, display_name?}`；整表替换的增删改；空清单允许并提示；重复（去空白后精确相同）返回 422 并指出重复项；`display_name` 空串归一为 `null`；测试覆盖空 / 重复 / 超长 / 大小写。
- [ ] T5 删除保护与复用关系：`used_by` 返回占用工具（含已卸载）；未确认删除 409 `PROFILE_IN_USE` 且 message 列出占用方；确认后删除档案 + 全部绑定 + 密钥；同一档案绑定两个工具；同一工具切换档案只保留新绑定；重复绑定幂等、重复解绑 `removed=false`；测试前后工具配置 hash 不变。
- [ ] T6 前端档案管理页：`api/profiles.ts` + `stores/profiles.ts`；`/profiles` 路由与「档案」导航；列表 / 空态 / 加载 / 错误 / 刷新失败；表单区分档案与凭证，编辑密钥留空保持、显式清除；模型编辑器增删改 / 空清单 / 重复提示；复制；删除占用确认框；绑定面板与「已绑定，尚未应用」；回退 banner；Vitest 用 `getByRole` / `getByText`，不新增依赖。
- [ ] T7 文档、手动验收与交接：README 补 `/profiles`、API、`profiles.json` / `secrets.json` 位置与备份、keyring 依赖与回退；PROGRESS 更新当前状态 / 下一个可执行命令；完成下方「手动验收」表；跑 `check.py` 并把完整输出贴到「验收记录」。

## 手动验收

> 涉及真实 OS keyring、浏览器界面与重启持久化，`check.py` 不能替代人工确认。实现完成后逐项填写「实际结果」。

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 新建一份带密钥的档案，保存后刷新页面 | 列表出现档案；只显示 `secret_preview`，无完整密钥；`profiles.json` 中只有 `secret_ref`，无明文；Windows 凭据管理器（或 `cmdkey /list`）出现 `cc-roster/<profile_id>` | 待填 |
| 2 | 编辑同一档案，密钥留空保存；再显式「清除密钥」保存 | 留空后密钥仍存在、预览不变；清除后 `has_secret=false`、预览为空，凭据管理器条目被删除 | 待填 |
| 3 | 把同一份档案绑定到 Claude Code 与 Codex CLI 两个工具 | 两个工具都出现在 `used_by`；绑定面板显示两个工具，均标注「已绑定，尚未应用」；工具配置文件未变化 | 待填 |
| 4 | 重启后端，再打开 `/profiles` | 档案、模型清单、绑定关系、密钥状态全部保留 | 待填 |
| 5 | 删除被两个工具占用的档案：先取消，再确认 | 取消时磁盘零变化；未确认返回占用提示并列出两个工具；确认后档案 / 绑定 / 密钥删除，工具配置文件 hash 不变 | 待填 |
| 6 | 复制一份带密钥的档案 | 生成新 ID、新名称、相同协议 / 地址 / 模型 / 密钥；原档案不变；复制品不带绑定 | 待填 |
| 7 | 用 `CC_ROSTER_SECRET_BACKEND=file` 启动后端并打开 `/profiles` | 页面显示「系统钥匙串不可用，密钥保存在本机文件」banner；新建 / 编辑 / 删除密钥正常；Unix 下 `secrets.json` 权限为 `0600` | 待填 |
| 8 | 手工把 `profiles.json` 改坏后打开 `/profiles`，再恢复备份 | 显示可读错误、不覆盖坏文件；恢复后列表正常；界面 / 响应中无明文密钥、无 traceback | 待填 |
| 9 | 用键盘和窄窗口（约 320px）操作新建 / 编辑 / 删除 / 绑定 | 表单可用 Tab 到达，focus 可见；无横向滚动；dialog 可用键盘关闭 / 确认 | 待填 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
待填
```