# 025 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 新增 `backend/tests/conftest.py` autouse fixture，统一隔离三平台数据目录。
- [x] T2 让 `test_settings_api.py` 用 `resolve_data_dir()` 推导 settings 路径。
- [x] T3 运行 settings / snapshots 相关测试，确认只读状态不再跨测试泄漏。
- [x] T4 运行 `uv run python scripts/check.py` 并记录完整输出。

## 验收记录

T3 命令：`cd backend && uv run pytest tests/test_settings_api.py tests/test_snapshots_api.py tests/test_paths.py tests/test_release_baseline.py tests/test_degradation_matrix.py tests/test_secret_scan.py -q`

```text
.....................................................                    [100%]
53 passed, 1 warning in 4.58s
```

T4 命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/025-ci-test-isolation (1 path rules)
[ok] 6 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
153 files already formatted

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
640 passed, 1 warning in 21.22s

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
   Start at  17:23:10
   Duration  1.91s (transform 595ms, setup 0ms, import 1.09s, tests 204ms, environment 2.84s)

All checks passed.
```