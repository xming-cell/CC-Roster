# 007 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 快照模型与内容寻址存储：`Snapshot` / `SnapshotFile` / `SnapshotChange` 与视图模型；`<data>/snapshots/<id>/meta.json` + `objects/<sha256前2位>/<sha256>`；按可注入块大小分块、整文件 hash + 块 hash、去重、空文件 / 缺失文件；损坏 / 未知版本列表降级、详情报错；Unix 0700 / 0600；UUID 路径防穿越；测试覆盖分块边界、篡改、坏 meta、不创建目录。
- [x] T2 保留策略与 pin：`Settings.snapshot_retention`（`CC_ROSTER_SNAPSHOT_RETENTION`，默认 20，1–1000）；按工具保留最近 N 份未 pin 快照；pin / unpin 幂等；回滚目标受保护；清理后回收无人引用的对象；测试覆盖 pin 超额、跨工具隔离、对象引用计数。
- [x] T3 外部改动检测：`FileObservation` 与 `observe_file`；存在 / 缺失 / 内容变化三类冲突；仅 mtime 变化不算冲突；结构化 `FileConflict` / `WriteConflict`；写前最终再校验；测试覆盖外部改内容、删除、新建与并发写。
- [x] T4 原子写与回读还原：`write_bytes_atomic`（临时文件 + fsync + `os.replace`，保留权限 / 新文件 0600）；`WriteEngine.apply` 在写锁内完成冲突检查 → 预快照 → 逐文件写 → 回读逐字节校验 → 审计；失败 / 回读不一致 / 审计失败时用预快照还原全部文件；多文件全有或全无；测试覆盖 replace 失败、回读损坏、第二文件失败、还原失败。
- [x] T5 保真编辑助手：`app/core/format_edits.py`；JSON 区间替换 / 插入 / 删除且不整份重排；TOML 用 `tomlkit` 保留注释 / 键序 / 未知字段；`KEY=VALUE` 行编辑；BOM / CRLF / Unicode / 空文件；`verify_rendered`；重复键 / 非法格式 / 非 UTF-8 → `UNSAFE_WRITE` 且零写入；测试用逐字节 fixture。
- [x] T6 快照 API 与回滚：`SnapshotService` + `/api/snapshots` 列表 / 详情 / `PATCH` pin / `POST .../rollback`；回滚前完整校验 chunk、预快照当前状态、逐文件恢复并校验、失败全部还原；响应不含原文 / chunk；`TestClient` 覆盖正常、404、422、损坏、空库、limit、多次回滚、回滚后逐字节一致。
- [x] T7 审计、文档与交接：`APP_MIGRATIONS` v1 `audit_entries` 与 `AuditRepository`；apply / rollback 记录文件 / 字段 / 快照 ID / 结果并脱敏；`initialize_app_data` 应用迁移；README 补快照布局、保留策略、API、安全边界、手动 curl 验收；PROGRESS 交接；跑 `check.py` 贴完整输出。

## 手动验收

> 本卡没有 UI / 终端 / 外部接口；用临时目录 + curl 对真实文件系统验证逐字节回滚与 pin 语义。

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 用临时文件（含 CRLF / BOM / 注释）走一次 `WriteEngine.apply`，记录原始 `Get-FileHash` / `sha256` | 写入前生成快照；快照列表能看到时间、文件、hash、变更摘要 | 通过（真实临时目录）：捕获快照 `5aa38b49-7886-4547-9d65-dc290ffd831f`；目标 29 字节 `BOM + CRLF + # comment`，原始 SHA-256 `7b023b5c…a7aaa`；`GET /api/snapshots` 返回 `created_at`、文件路径 / hash / 大小、`model: old → new` 变更摘要与 `retention_limit=20` |
| 2 | 故意让回读校验失败（测试注入），再检查目标文件 | 返回失败；目标文件恢复为写入前字节；无半截临时文件 | 通过：`test_apply_readback_mismatch_restores_every_file` 注入第二次回读损坏，返回 `WRITE_VERIFY_FAILED`，a.json / b.json 均恢复原字节，消息含期望 / 实际 hash |
| 3 | 写入后手工改目标文件，再用旧观察值 apply | 返回 `WRITE_CONFLICT`；目标文件不被覆盖；详情含路径与两边 hash | 通过：`test_second_apply_with_stale_observation_conflicts` 返回 `WRITE_CONFLICT`（409），目标保持 `v1`，冲突详情含路径与 hash；另有 MISSING / CREATED / CONTENT_CHANGED 三类用例 |
| 4 | 调用 `POST /api/snapshots/{id}/rollback`，对比原始文件 | 生成预回滚快照；目标文件与快照时逐字节一致（`cmp` / hash 相同） | 通过（真实 uvicorn + curl）：先把文件改成 `tampered externally`，回滚响应 `action=restored`，生成预回滚快照 `02744d5b-…`；回滚后 SHA-256 回到 `7b023b5c…a7aaa`，hex `efbbbf2320636f6d6d656e740d0a6d6f64656c203d20226f6c64220d0a` 与原始一致 |
| 5 | pin 一份最旧快照，再连续写入超过保留上限 | pin 的快照仍在；最旧的未 pin 快照被清理；对象目录无残留引用 | 通过：`PATCH` pin `5aa38b49-…` 后连续 21 次真实 `WriteEngine.apply`；总数 20（含 pin）、pin 仍在、旧未 pin `02744d5b-…` 被清理，`orphan_objects=[]` |
| 6 | 删除 `db/app.sqlite3` 后重启，再列出快照 | 快照仍可列表 / 回滚；审计表自动重建；工具配置未变 | 通过：删除 DB 后 `initialize_app_data` 重建 `audit_entries`；20 份快照仍可列表且 pin 保留；回滚 `5aa38b49-…` 成功并恢复 `7b023b5c…a7aaa`，目标文件未因删库改变 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/007-snapshot-kernel (5 path rules)
[ok] 34 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
78 files already formatted

=== backend types ===
Success: no issues found in 41 source files

=== backend tests ===
........................................................................ [ 15%]
........................................................................ [ 31%]
........................................................................ [ 47%]
........................................................................ [ 63%]
........................................................................ [ 79%]
........................................................................ [ 94%]
.......................                                                  [100%]
=============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\ҵļ\Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
455 passed, 1 warning in 17.36s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  6 passed (6)
      Tests  50 passed (50)
   Start at  20:33:53
   Duration  11.63s (transform 6.64s, setup 0ms, import 10.03s, tests 2.12s, environment 42.02s)


All checks passed.
```