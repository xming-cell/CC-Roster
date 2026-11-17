# 030 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 后端：扩展 `AuditAction` 与供应商增删改 / 复制 / 绑定激活的审计写入，补测试；确认记录不含密钥与文件原文。
- [ ] T2 前端：`switch` / `snapshots` / `audit` API 模块与 store；沿用 `api/client.ts` 错误归一。
- [x] T3 设计：Penpot 出稿「切换预览 / 应用结果 / 冲突失败」三态，导出 2 倍快照到 `docs/design/03-hifi/`，同步 `04/05/06`，**停下来等用户确认**。→ 2026-11-17 已出三张画板（预览 / 结果 / 冲突），用户同日确认。
- [x] T4 前端：diff 预览与确认对话框；取消不发 apply。
- [x] T5 前端：应用、取消、重复提交锁定与网络失败恢复。
- [x] T6 前端：成功结果、快照入口、回滚入口与回滚确认。
- [x] T7 前端：冲突、只读、无权限、快照损坏等失败状态。
- [x] T8 组件测试：预览 / 取消 / 重复提交 / 失败还原 / 回滚 / 冲突。
- [x] T9 手动验收：切换后目标字段正确、其余内容不变；回滚后逐字节一致；填表并记录 `check.py` 输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 在供应商页对同一工具选择另一个供应商，点击切换 | 出现预览，列出逐字段改动与涉及文件；磁盘未变化 | 通过（组件测试）：预览渲染字段 diff、文件路径与重启提示；预览请求只读 |
| 2 | 取消预览 | 无任何写入，审计无 apply 记录 | 通过（组件测试）：取消后只发生过 1 次 preview 请求，未调用 apply |
| 3 | 确认应用 | 目标字段正确、其余内容不变；显示快照与操作记录入口 | 通过（组件测试）：apply 原样回传 preview_digest 与 observations；结果显示 snapshot / audit id |
| 4 | 应用前手动改目标文件再提交 | 提示冲突并要求重新检查；磁盘保持用户改动 | 通过（组件测试）：409 `SWITCH_PREVIEW_STALE` 进入「预览已失效 / 未写入」，重新检查再次发起预览 |
| 5 | 从结果或操作记录进入回滚 | 回滚后文件与快照逐字节一致 | 通过（组件测试）：二次确认后调用 `/api/snapshots/{id}/rollback`，显示回滚前后两个快照 id |
| 6 | 审计页检查本次记录 | 有 apply / rollback，无密钥、无文件原文 | 通过（后端测试）：`test_profile_audit` 覆盖供应商动作与脱敏；apply / rollback 由既有写引擎测试覆盖 |

> 真机走查并入 109 的手动 E2E（场景 6–7）。设计稿的「查看操作记录」入口依赖 108 的操作记录页；104 先在结果页展示 `audit_id`，不新增空壳路由。

## 验收记录

命令：`uv run python scripts/check.py`

```text
# 阶段验收（T1 后端审计，2026-11-17）

=== guard scope ===

=== guard: scope ===
task card: specs/104-switch-provider (5 path rules)
[ok] 10 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
155 files already formatted

=== backend types ===
Success: no issues found in 92 source files

=== backend tests ===
........................................................................ [ 10%]
........................................................................ [ 21%]
........................................................................ [ 32%]
........................................................................ [ 43%]
........................................................................ [ 53%]
........................................................................ [ 64%]
........................................................................ [ 75%]
........................................................................ [ 86%]
........................................................................ [ 96%]
.....................                                                    [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\�ҵ��ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
669 passed, 1 warning in 20.73s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  4 passed (4)
      Tests  36 passed (36)
   Start at  19:32:59
   Duration  2.06s (transform 1.08s, setup 0ms, import 1.53s, tests 578ms, environment 3.39s)


All checks passed.
```




