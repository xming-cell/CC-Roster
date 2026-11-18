# 028 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 数据完整性：`ProfileStore` 允许同一工具多条绑定，`(tool_id, profile_id)` 唯一，同一工具最多一条 `active=true`；保留档案引用校验；旧单绑定 v1 数据可直接读取。
- [x] T2 绑定语义：`bind_tool` / `PUT /api/tools/{tool_id}/profile` 新增绑定而不删除同工具其他绑定；同供应商重复绑定幂等；未知工具 / 档案保持 404。
- [x] T3 精确解绑：新增 `DELETE /api/tools/{tool_id}/profiles/{profile_id}`（或等价的必须指定 profile 的安全接口）；只删指定绑定，`removed=false` 幂等；解绑 active 后不自动提升其他绑定。
- [x] T4 切换与应用：`SwitchService._save_binding` 只切换目标 binding 的 active 状态，保留其他绑定；保留 `bound_at`；A→B→A 后绑定不丢；失败 / 回滚不留下两条 active。
- [x] T5 删除保护与查询：删除供应商检查全部绑定（含已卸载工具，`installed=false`）；`GET /api/profiles?tool_id=` 返回指定工具的绑定与供应商；未过滤时保持全量行为。
- [x] T6 测试：多绑定、重复绑定幂等、单 active、双 active 拒绝、A→B→A、精确解绑、已卸载工具删除保护、旧 v1 数据、未知 ID、并发锁下不丢绑定。
- [x] T7 手动验收：用 TestClient 创建 A/B 两个供应商，绑定同一工具后依次应用 A、B、A，核对绑定数量、active、bound_at、applied_at、snapshot_id；验证删除保护与精确解绑；填写下方验收表并记录 `check.py` 完整输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 创建供应商 A / B，用 `PUT /api/tools/claude-code/profile` 分别绑定到同一工具 | 返回两条不同绑定，均 `active=false`，A / B 都保留 | 通过：两次 PUT 均 200；`bindings` 数量 2，`active` 为 `[false, false]`；两条 `bound_at` 分别为 `2026-11-17T09:55:31.516395Z` / `...529805Z` |
| 2 | `GET /api/profiles?tool_id=claude-code` | 只返回该工具的供应商与两条绑定 | 通过：`profiles` 为 `Alpha`、`Beta`；`bindings` 两条且 `tool_id` 均为 `claude-code` |
| 3 | 通过现有切换 / 应用接口依次应用 A、B、A | 两条绑定始终保留；每次恰好一条 active；`bound_at` 不变，`applied_at` / `snapshot_id` 指向最后一次成功应用 | 通过：A1 后 A active / B inactive；B 后 A inactive / B active；A2 后 A active / B inactive。A 的 `bound_at` 始终为 `2026-11-17T09:55:31.516395+00:00`，B 为 `...529805+00:00`；A2 的 `applied_at` / `snapshot_id` 更新为 `2026-11-17T09:55:31.646827+00:00` / `9a07502a-aa5a-4451-a243-b59a1b82e716`，B 保持 B 次应用的 `d6063bb1-c76d-4918-87dc-4b41176cdec0` |
| 4 | `DELETE /api/tools/claude-code/profiles/{B}` | 只移除 B；A 及其状态保持不变；重复解绑返回 `removed=false` | 通过：首次 `removed=true`，重复 `removed=false`；剩余仅 A，A 的 `active`、`bound_at`、`applied_at`、`snapshot_id` 均未变化；供应商 A 仍存在 |
| 5 | 将供应商 A 绑定到 Claude 与 Codex，再删除 A | 未确认时 409 `PROFILE_IN_USE`，`used_by` 含两个工具；确认后只清理 A 的绑定，B 不受影响 | 通过：未确认返回 409 `PROFILE_IN_USE`，消息同时包含 `Claude Code`、`Codex CLI`；确认后 `unbound_tools` 含两个工具，剩余绑定仅 B→`claude-code`，B 仍存在 |
| 6 | 删除工具安装目录但保留历史绑定，再删除对应供应商 | 仍返回 409，`used_by` 含 `installed=false`；确认删除不报 traceback | 通过：删除 `codex` 配置目录后，详情 `used_by` 为 `codex-cli` / `installed=false`；删除未确认 409 `PROFILE_IN_USE`，确认后成功清理，无 traceback |
| 7 | 读取一份旧版单绑定 `profiles.json` | 列表、详情、切换均可用；文件不被主动改写；无 schema 版本错误 | 通过：列表 200（1 个供应商）、详情 200；列表 / 详情 / 预览前后文件 hash 与 mtime 不变；应用 200，绑定数 1、active=true，`bound_at` 保持 `2026-11-01T00:00:00+00:00`，`schema_version` 仍为 1 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/102-multi-provider-bindings (2 path rules)
[ok] 11 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
154 files already formatted

=== backend types ===
Success: no issues found in 92 source files

=== backend tests ===
........................................................................ [ 10%]
........................................................................ [ 21%]
........................................................................ [ 32%]
........................................................................ [ 43%]
........................................................................ [ 54%]
........................................................................ [ 65%]
........................................................................ [ 76%]
........................................................................ [ 86%]
........................................................................ [ 97%]
...............                                                          [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\我的文件夹\项目3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
663 passed, 1 warning in 17.14s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  3 passed (3)
      Tests  23 passed (23)
   Start at  17:58:03
   Duration  1.80s (transform 624ms, setup 0ms, import 931ms, tests 204ms, environment 2.43s)


All checks passed.
```
