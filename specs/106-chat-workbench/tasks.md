# 032 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 核实 Claude Code / Codex CLI / Gemini CLI / OpenCode 的思考强度参数与取值，形成能力表并注明出处；无法确认的标「不支持」，不猜。
- [x] T2 后端：`ChatSession` / `ChatCreateRequest` / 命令构造增加思考强度，按能力映射；不支持时明确拒绝或忽略并写测试。
- [x] T3 后端：补 fake executor 下的能力 / 非法取值 / 会话恢复测试。
- [x] T4 前端：chat / sessions API 模块、SSE 解析、store。
- [x] T5 设计（修订 A）：去掉新建会话对话框；出「对话工作台 · 折叠态 / 展开态 / 上下文切换」画板，导出快照，**停下来等用户确认**。2026-11-17 按改向重做并获用户确认。
- [x] T5b 后端：`ChatSession.model` + `PATCH /api/chat/sessions/{id}`（模型 / 强度，按清单与能力表校验）。
- [x] T6 前端：会话列表、工具头「+」一键新建（目录取该工具最近会话，首次才询问）。
- [x] T7 前端：上下文条内联切换模型 / 思考强度，作用于后续消息。
- [x] T8 前端：消息区、折叠过程行、展开/收起、完成摘要、流式与停止。
- [x] T9 前端：失败重试、不支持对话降级、重复提交锁定。
- [x] T10 组件测试与手动验收并记录 `check.py` 输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 已有历史会话时点击工具头「+」 | 直接创建新会话，项目目录沿用该工具最近会话，不弹对话框 | 通过（组件测试）：POST 直接带 `remembered project_dir` |
| 2 | 该工具第一次使用（无历史会话） | 只询问一次项目目录；提交后创建成功 | 通过（组件测试）：仅此时出现目录输入框，提交带 `profile_id` 与目录 |
| 3 | 上下文条切换模型 | 模型菜单只列供应商清单；PATCH 成功，下一条消息使用新模型 | 通过（前后端测试）：PATCH `model` 校验清单；命令带 `--model` |
| 4 | 切换思考强度 / 查看不支持的工具 | 只列能力档位；Gemini / OpenCode 不显示胶囊 | 通过（组件 + 后端测试）：能力表驱动；无能力时隐藏 |
| 5 | 发送消息 | 思考 / 工具调用默认折叠，点击展开原始命令与输出；流式 token 可见 | 通过（组件测试）：默认折叠、点击展开、SSE 半包解析 |
| 6 | 完成 / 失败 / 停止 | 完成后过程折叠只留回答；失败保留输入可重试；停止可用 | 通过（组件测试）：失败卡与停止按钮渲染；真机走查并入 109 |
| 7 | 工具不支持应用内对话 | 只显示说明，不渲染输入框 | 通过（组件测试）：`textarea` 不存在 |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/106-chat-workbench (5 path rules)
[ok] 19 changed file(s), all within scope

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
687 passed, 1 warning in 22.15s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  8 passed (8)
      Tests  57 passed (57)
   Start at  20:50:44
   Duration  4.10s (transform 4.39s, setup 0ms, import 6.91s, tests 2.26s, environment 12.81s)


All checks passed.
```




