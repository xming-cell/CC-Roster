# 008 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

## 前置检查

- [x] 开工前重读 `rules/backend.md`、`rules/frontend.md`、`rules/testing.md`、`rules/git.md`、`PROGRESS.md`；确认 `specs/CURRENT` 指向本卡。
- [x] 确认工作区没有 007 之外的未提交改动；`uv run python scripts/check.py` 当前为绿，记录基线。

## 任务

- [x] T1 适配器写契约与共享渲染：`app/adapters/base.py` 增加 `supported_protocols`、`plan` / `render` / `verify` 与内部 `ToolCurrentFile` / `ToolPlanFile`；新增共享 `ManagedFieldsAdapter` helper（复用 `format_edits.render_document` / `verify_rendered`，补未知内容校验）；`claude_code.py` / `codex_cli.py` 实现映射；capabilities 升为 `write=true` / `write_mode="managed_fields"`。测试：`test_switch_contract.py`（计划零写、render 纯函数 / 确定性、BOM / CRLF / 注释 / 键序 / 未知字段保留、verify 篡改检测、`UNSAFE_WRITE`、协议列表），两个适配器各一组映射测试（缺失文件、现有凭证优先级、模型优先级、`env_key` 冲突、OAuth warning、密钥脱敏、重启文案）。真实 Codex 配置行为在 T8 手动确认。
- [x] T2 预览 API：`app/schemas/switch.py` 的请求 / 响应 / blocker / warning / 文件预览模型；`SwitchService.preview`（工具存在且安装、协议、模型默认 / 选择 / 非法、密钥读取、`read_file_with_bytes`、`adapter.plan` / `render` / `verify`、`preview_digest`、`can_apply`）；`POST /api/switch/preview` 与依赖注入；挂载 `app/main.py`。测试：正常预览、模型默认第一项、空清单保持当前模型、非法模型 422、协议不匹配 blocker、缺失 / 异常密钥、损坏文件、只读 / 无权限 blocker、预览前后文件 hash / 快照目录 / 审计表完全不变、响应无明文密钥。
- [x] T3 应用 API：`SwitchService.apply`（重算并比对 digest、blockers → 409、observations 校验、构造 `WritePlan`、`WriteEngine.apply`、`ProfileRepository.mutate` 更新绑定、`updated_at` 再校验、绑定失败自动 `SnapshotService.rollback`）；`POST /api/switch/apply`。测试：成功写入目标字段且其余字节不变、快照 / 审计 / 绑定齐全、重启要求、过期 digest 零写、外部改动 `WRITE_CONFLICT`、档案过期 / 删除、绑定失败回滚成功 / 回滚失败、审计失败还原、并发 apply、锁超时、响应 / 审计 / 快照 meta / 日志无明文密钥。
- [x] T4 冲突与可读失败：`app/core/errors.py` 增加 `ErrorDetails` / `details`；`error_handlers.py` 序列化 `exclude_none=True`，`WriteConflict` 带 `conflicts`，`SWITCH_PREVIEW_STALE` 带 `stale_paths`；补齐 `SWITCH_BLOCKED` / `BINDING_WRITE_FAILED` / `APPLY_ROLLBACK_FAILED`。测试：既有 `{code, message}` 形状不变、新 details 字段、MISSING / CREATED / CONTENT_CHANGED 三类冲突、只读文件 / 无权限目录 / 损坏配置的 blocker、apply 零写、无自动合并。
- [x] T5 审计 API：`app/schemas/audit.py` 列表模型、`AuditRepository.list_recent` 复用、`GET /api/audit?tool_id=&limit=`（默认 50、1–200）、未知工具空列表、读取失败 500；测试：成功 / 失败 / 冲突记录、工具过滤、limit 上下界、空库、脱敏、排序稳定。
- [x] T6 前端预览确认：`api/switch.ts`、`stores/switches.ts`、`components/SwitchPanel.vue`、`components/SwitchPreviewDialog.vue`；档案 / 模型选择、预览、字段级 before / after、blockers / warnings、重启提示、取消零请求、确认 apply、成功刷新、冲突显示详情 + 重新预览、慢请求 / 双击 / 超时、键盘与 aria。`api/client.ts` 增加 `details` 解析与测试。组件测试 `SwitchPanel.spec.ts` / `SwitchPreviewDialog.spec.ts`。
- [x] T7 前端快照与绑定状态：`api/snapshots.ts`、`stores/snapshots.ts`、`components/SnapshotPanel.vue`；列表、空状态、warnings、pin / unpin、确认回滚、成功刷新、失败不假成功、不提供下载；`HomeView.vue` 接入「切换档案」与「快照 / 回滚」；`BindingPanel.vue` / `ProfilesView.vue` 显示已应用 / 尚未应用 / 档案已修改，移除「切换在 008 实现」。测试 `SnapshotPanel.spec.ts`，更新 `HomeView.spec.ts` / `ProfilesView.spec.ts`；断言变更理由写进 `PROGRESS.md`。
- [x] T8 文档、手动验收与收尾：README 补 API / 切换流程 / 密钥边界 / 冲突 / 重启 / 快照 UI / 手动 curl；临时 `CLAUDE_CONFIG_DIR` / `CODEX_HOME` 完成 8 项手动验收；真实 Codex 启动确认 provider / model / key（不可行时记录原因与替代验证）；`PROGRESS.md` 交接；跑 `uv run python scripts/check.py` 并把完整输出贴到下方。

## 手动验收

> 使用临时 `CLAUDE_CONFIG_DIR` / `CODEX_HOME`，不碰真实用户配置；涉及真实 Codex 的项记录实际命令与结果。

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 打开主界面选中工具，点「预览改动」，对比预览前后目标文件 hash、`snapshots/`、审计条数 | 预览只读；hash / 快照目录 / 审计数量完全不变；逐字段 before / after 可见 | 正常 |
| 2 | 确认应用，检查目标字段、其余字节、快照 / 审计 / 绑定 | 目标字段符合预期；其余内容逐字符不变；快照、审计、绑定均可追溯；重启提示可见 | 正常 |
| 3 | 预览后手工改目标文件，再点确认 | 409 `WRITE_CONFLICT`；冲突文件 / 原因可见；文件未被覆盖；重新预览后可再次应用 | 正常 |
| 4 | 把目标文件设为只读 / 父目录设为无权限，预览并尝试应用 | 预览显示 blocker 或可读错误；apply 零写入；无半截临时文件 | 正常 |
| 5 | 预览后点取消 | 无 apply 请求；磁盘零变化；再次预览仍可应用 | 正常 |
| 6 | 应用后回滚，对比 apply 前 hash | 回滚前自动快照；文件逐字节一致（`Get-FileHash` / `sha256sum` / `cmp`） | 正常 |
| 7 | 临时 `CODEX_HOME` 下用真实 Codex 启动，读取 provider / model / key | Codex 读到所选值；若版本不读 `auth.json` 或 OAuth 优先，记录实测并调整映射，不静默失败 | 正常 |
| 8 | 窄屏（< 768px）、键盘 Tab / Enter / Esc、空状态、blocker、warnings | 布局可用；焦点可见；取消 / 确认 / 重新预览可键盘操作；无假成功 | 正常 |

> 8 项验收由用户于 2026-11-11 手动完成并确认「正常」；第 7 项真实 Codex 验证的命令与版本以用户本地记录为准。

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/008-switch-preview (4 path rules)
[ok] 45 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
90 files already formatted

=== backend types ===
Success: no issues found in 47 source files

=== backend tests ===
........................................................................ [ 13%]
........................................................................ [ 26%]
........................................................................ [ 40%]
........................................................................ [ 53%]
........................................................................ [ 67%]
........................................................................ [ 80%]
........................................................................ [ 94%]
..............................                                           [100%]
=============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\我的文件夹\项目3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
534 passed, 1 warning in 15.15s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  9 passed (9)
      Tests  80 passed (80)
   Start at  22:44:05
   Duration  10.50s (transform 7.41s, setup 0ms, import 13.66s, tests 4.15s, environment 55.41s)


All checks passed.
```

## 已确认的开卡决策

1. 密钥写入工具配置；预览 / API / 日志 / 错误 / 审计 / 快照 meta 全部脱敏，快照原始 blob 不提供下载。
2. Claude Code 只接受 `anthropic`，Codex CLI 只接受 `openai`；不匹配即 blocker，零写入。
3. 模型默认档案清单第一项；预览可选清单内其他模型；清单为空保持当前模型。
4. 切换与快照 UI 放主界面详情；`/profiles` 只保留并修正绑定状态。
5. 预览无状态：`preview_digest` + 文件观察值；apply 重算比对；冲突不自动合并。
6. 诚实成功：写引擎回读、审计、绑定都成功才成功；绑定失败自动回滚。
7. 错误响应增加可选 `details`，旧形状不变。
8. Codex 用内置 `openai` provider 覆盖；`responses` / `chat` 按 host 选择；真实行为手动确认。
9. 不新增依赖；不扩展 scope；歧义先问用户。

## 风险与待确认

- **Codex 真实行为**：不同版本可能优先 OAuth、忽略 `auth.json` 或对 `wire_api` 有额外要求；T8 已由用户在临时 `CODEX_HOME` 下用真实 Codex 验证并确认「正常」，读到所选 provider / model / key，映射无需调整。后续版本变化需重新确认。
- **权限测试跨平台**：Unix `chmod` / `os.access` 与 Windows ACL 行为不同；POSIX-only 断言用 `pytest.mark.skipif`（不是无理由 `.skip`），Windows 用可注入的失败点测试错误路径。
- **既有测试改动**：`capabilities.write` 与档案页文案是行为变更，必须同步断言并在 `PROGRESS.md` 写理由；不得为了变绿改断言。
- **快照含旧密钥**：原始 blob 可能含写入前密钥；不新增下载 / 导出接口，README 明确备份与访问边界。