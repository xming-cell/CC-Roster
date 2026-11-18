# 038 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 后端：能力表增加 `resume`，Claude / Codex 置 true。
- [x] T2 后端：会话字段 `resume_from_tool_id` / `resume_from_session_id`，命令构造与校验。
- [x] T3 后端测试：命令映射、未知会话、非支持工具；清理被禁用的类型忽略注释。
- [x] T4 设计：历史时间线底部输入框 + 模型 / 强度选择器，画板经用户确认。
- [x] T5 前端：输入并发送时创建带 resume 字段的新会话，切到对话视图并显示成功提示；不输入保持只读。
- [x] T6 前端测试：输入框可见性、空输入、模型 / 强度默认值、创建字段、失败路径。
- [x] T7 完整验收并回填文档；真人追问走查留给 109。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 打开 Claude 历史，不输入 | 保持只读，不创建会话 | 通过：组件测试校验仅在发送时创建 |
| 2 | 在底部输入框输入并发送 | 新建续聊会话，切到对话视图并显示成功提示 | 通过：组件测试校验 resume 字段与成功提示 |
| 3 | 追问「刚才改到哪了」 | 回答能引用原会话上下文 | 待 109 真人走查 |
| 4 | 打开不支持的工具历史 | 不显示输入框，有只读说明 | 通过：组件测试校验 |
| 5 | 继续后检查原历史 | 仍可只读打开，顺序不变 | 通过：后端 hash 测试 + 前端只读回放 |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/112-resume-history (6 path rules)
[ok] 14 changed file(s), all within scope

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
709 passed, 1 warning in 23.98s

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
      Tests  86 passed (86)
   Start at  14:08:40
   Duration  9.02s


All checks passed.
```