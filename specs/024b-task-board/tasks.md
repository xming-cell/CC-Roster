# 024b 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 写 `docs/task-board.md`：状态图例、卡片总表、设计确认记录、固定流程。
- [x] T2 在 `docs/task-plan2.md` 顶部加总表入口与状态说明。
- [x] T3 建 104–109 六张任务卡（spec + tasks）。
- [x] T4 更新 `PROGRESS.md`，把总表写成唯一进度入口。
- [x] T5 跑 `check.py` 并回填验收记录。

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/024b-task-board (1 path rules)
[ok] 18 changed file(s), all within scope

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
  D:\�ҵ��ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
663 passed, 1 warning in 19.48s

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
   Start at  19:26:13
   Duration  2.06s (transform 1.21s, setup 0ms, import 1.69s, tests 559ms, environment 3.55s)


All checks passed.
```

