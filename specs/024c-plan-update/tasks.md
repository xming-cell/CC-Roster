# 024c 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 追加 ADR-015～017。
- [x] T2 建 110/036、111/037、112/038 三张卡。
- [x] T3 更新总表、任务计划与 105/106/107 修订说明。
- [x] T4 更新 PROGRESS。
- [x] T5 跑 `check.py` 并回填。

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/024c-plan-update (1 path rules)
[ok] 16 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
158 files already formatted

=== backend types ===
Success: no issues found in 94 source files

=== backend tests ===
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 31%]
........................................................................ [ 41%]
........................................................................ [ 52%]
........................................................................ [ 62%]
........................................................................ [ 73%]
........................................................................ [ 83%]
........................................................................ [ 94%]
.......................................                                  [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\�ҵ��ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
687 passed, 1 warning in 23.23s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  11 passed (11)
      Tests  66 passed (66)
   Start at  21:45:08
   Duration  4.50s (transform 6.79s, setup 0ms, import 10.14s, tests 2.85s, environment 18.78s)


All checks passed.
```

