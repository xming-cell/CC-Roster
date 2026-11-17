# 033 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 前端：sessions / 回放 API 模块与 store，沿用错误归一。
- [x] T2 设计：Penpot 出稿「历史会话列表 / 时间线 / 工具调用折叠 / 未知类型与错误」，导出快照，**停下来等用户确认**。→ 2026-11-17 已出 `会话历史 · 1440`，用户同日确认。
- [x] T3 前端：分组、分页、懒加载与切换竞态。
- [x] T4 前端：时间线五类渲染、未知类型降级、长内容折叠。
- [x] T5 前端：空 / 加载 / 部分失败 / 无权限状态。
- [x] T6 测试：只读 hash、分页、未知类型、竞态、性能口径。
- [x] T7 手动验收并记录 `check.py` 输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 打开历史页，选择有会话的工具 | 列表按项目 / 最近活动组织，未知项目显示「未知项目」 | 通过（组件测试）：按 project_path 分组，null 显示「未知项目」 |
| 2 | 打开昨天的一段真实对话 | 顺序与内容与原文件一致 | 通过（组件测试）：按响应顺序渲染 user / assistant / system；真机比对并入 109 |
| 3 | 查看含工具调用的会话 | 调用与结果成对、可折叠 | 通过（组件测试）：默认折叠，点击展开原始输出 |
| 4 | 打开一个损坏文件 | 该条降级，其它会话仍可看 | 通过（组件测试）：列表级 warnings 横幅；单条失败不影响其它条目 |
| 5 | 读取前后比对原始文件 hash | 完全一致 | 后端 012 已覆盖；前端没有任何写入口 |
| 6 | 上百会话翻页 | 无明显卡顿，滚动位置稳定 | 分页 API + 「加载更早」；真机性能并入 109 |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/106-chat-workbench (5 path rules)
[ok] 15 changed file(s), all within scope

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
687 passed, 1 warning in 22.59s

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
   Start at  21:24:50
   Duration  4.34s (transform 5.72s, setup 0ms, import 10.28s, tests 2.17s, environment 19.21s)


All checks passed.
```


