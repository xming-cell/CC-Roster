# 037 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 后端：`pick-directory` 端点与三平台命令构造、超时、501 降级。
- [x] T2 后端测试：命令构造、取消、不可用、并发点击。
- [x] T3 设计：目录对话框加「浏览…」按钮（小改，导出快照）。
- [x] T4 前端：按钮 + 回填 + 错误提示。
- [x] T5 手动验收（Windows 真实弹窗）并回填 `check.py` 输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 新建会话 → 浏览… | 弹出系统文件夹选择器 | 通过：Windows 真实弹窗已打开 |
| 2 | 选择目录 | 路径回填输入框，创建成功 | 通过：组件测试校验回填与显式创建 |
| 3 | 取消选择 | 输入不变，无错误 | 通过：真实弹窗取消返回 `cancelled=true` |
| 4 | 连续点击两次 | 只弹一次 | 通过：组件测试校验第二次点击被禁用 |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/111-directory-picker (5 path rules)
[ok] 17 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
165 files already formatted

=== backend types ===
Success: no issues found in 97 source files

=== backend tests ===
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 30%]
........................................................................ [ 40%]
........................................................................ [ 51%]
........................................................................ [ 61%]
........................................................................ [ 71%]
........................................................................ [ 81%]
........................................................................ [ 91%]
.........................................................                [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\�ҵ��ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
705 passed, 1 warning in 20.31s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  15 passed (15)
      Tests  82 passed (82)
   Start at  23:30:24
   Duration  6.30s (transform 9.24s, setup 0ms, import 15.80s, tests 3.27s, environment 46.09s)


All checks passed.
```
