# 024 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 盘点当前后端能力、前端现状、设计文档与旧任务卡，确认 V2 的真实起点。
- [x] T2 整理待拍板决策（档案语义、多供应商、项目、思考强度、导入、快照入口、审计范围、旧功能取舍）。
- [x] T3 写出 `docs/task-plan2.md`：任务卡总览、依赖、里程碑、详细卡、旧卡映射与风险。
- [x] T4 运行 `uv run python scripts/check.py` 并记录完整输出。

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/024-replan-v2 (2 path rules)
[ok] 6 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
152 files already formatted

=== backend types ===
Success: no issues found in 92 source files

=== backend tests ===
........................................................................ [ 11%]
........................................................................ [ 22%]
........................................................................ [ 33%]
........................................................................ [ 45%]
........................................................................ [ 56%]
........................................................................ [ 67%]
........................................................................ [ 78%]
........................................................................ [ 90%]
................................................................         [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\我的文件夹\项目3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
640 passed, 1 warning in 36.01s

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
      Tests  15 passed (15)
   Start at  16:22:42
   Duration  3.11s (transform 889ms, setup 0ms, import 1.50s, tests 366ms, environment 4.92s)

All checks passed.
```