# 026 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 供应商语义（D-9）与后端 `Profile` 命名策略（D-17）→ ADR-009（D-9B 否决）。
- [x] T2 多供应商绑定、项目、思考强度、本地导入、快照入口、审计范围、旧功能取舍 → ADR-010～ADR-014。
- [x] T3 写 `docs/design/04-tokens.md`：颜色、字号、间距、圆角、阴影、动效、状态色与亮 / 暗模式策略。
- [x] T4 写 `docs/design/05-components.md`：组件清单、状态矩阵、可访问性要求。
- [x] T5 写 `docs/design/06-acceptance.md`：页面级验收清单与手动验收场景。
- [x] T3b 写 `docs/design/07-design-source.md`：Penpot 源文件信息、快照规范、导出代码只作标尺。
- [x] T3c 建立 `docs/design/03-hifi/`：快照命名规范与导出步骤（图片待 Penpot 导出后补入）。
- [x] T3d 术语统一：IA 与画板中的「档案」改为「供应商」，移除列表面板搜索框（依据 D-17 方向与用户 2026-11-16 决定）。
- [x] T6 更新 `docs/decisions.md`、`docs/task-plan2.md`、`PROGRESS.md`；跑 `check.py` 并记录完整输出。

## 手动验收

> 与用户逐项过 D-9～D-17。没有确认的决策不得标为已完成。

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 逐条过 D-9 / D-9B / D-10 / D-17 | 语义、绑定模型、后端命名有唯一结论 | 已确认：D-9 选 A、D-9B 否决、D-10 采纳、D-17 不重命名（ADR-009/010） |
| 2 | 逐条过 D-11 / D-12 / D-13 | 思考强度、项目派生、导入格式有唯一结论 | 已确认（ADR-011/012） |
| 3 | 逐条过 D-14 / D-15 / D-16 | 快照入口、审计范围、延后功能有唯一结论 | 已确认（ADR-013/014） |
| 4 | 检查 tokens / components / acceptance 三份文档 | 覆盖 DoD 列出的全部条目 | 已通过；另补 `03-hifi/` 快照与 `07-design-source.md` |
| 5 | 术语与范围同步 | 界面、文档、计划文件一致 | 「档案」统一为「供应商」；搜索框移除并写入 ADR-014；`task-plan2.md` 升为 v0.2 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===
task card: specs/026-v2-decision-baseline (8 path rules)
[ok] 15 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
153 files already formatted

=== backend types ===
Success: no issues found in 92 source files

=== backend tests ===
640 passed, 1 warning in 22.18s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run
Test Files  3 passed (3)
     Tests  15 passed (15)

All checks passed.
```