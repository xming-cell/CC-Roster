# 039 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 后端：通用本机配置预览 / 导入端点，覆盖 Claude / Codex / Gemini / OpenCode。
- [x] T2 后端：本机配置绑定来源工具，文件导入绑定当前工具；导入后立即可见且 `active=false`。
- [x] T3 后端测试：四类工具映射、配置缺失 / 损坏、密钥边界、绑定与去重。
- [x] T4 设计：本机配置选择、Claude 预览、导入成功列表，画板经用户确认。
- [x] T5 前端：导入弹窗工具列表、预览、确认；导入后自动切换工具并刷新列表。
- [x] T6 前端测试：本机工具列表、Claude 导入、文件导入带 tool_id、自动切换。
- [x] T7 完整验收并回填文档；真人本机配置导入走查留给 109。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 打开导入弹窗，切到本机配置 | 列出 4 个工具；无配置的工具置灰 | 通过：组件测试校验 |
| 2 | 选择 Claude Code 并读取 | 预览 settings.json，只显示有 / 无密钥 | 通过：后端 + 组件测试 |
| 3 | 确认导入 | 自动切到 Claude Code，列表出现未启用条目 | 通过：绑定 + 自动切换测试 |
| 4 | 从文件导入 | 绑定当前选中工具，列表立即可见 | 通过：后端 tool_id 绑定测试 |
| 5 | 检查原配置文件与审计 | 文件 hash 不变，审计无密钥 | 通过：后端测试 |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/113-local-config-import (6 path rules)
[ok] 14 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
166 files already formatted

=== backend types ===
Success: no issues found in 97 source files

=== backend tests ===
714 passed, 1 warning in 38.42s

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
      Tests  87 passed (87)
   Start at  14:24:40
   Duration  9.38s


All checks passed.
```