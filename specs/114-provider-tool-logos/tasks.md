# 040 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 前端：`ProviderToolItem` 改用 `ToolLogo`，移除会覆盖品牌色的通用 SVG 样式。
- [x] T2 测试：供应商页已知工具显示品牌 logo，未知工具走 fallback。
- [x] T3 完整验收并回填 `check.py` 输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 打开供应商页 | 左侧工具列表显示 Claude / Codex 等品牌 logo | 通过：组件测试断言 `.tool-logo` 渲染 |
| 2 | 未知工具 | 显示统一 fallback，不出现空白或破图 | 通过：组件测试断言 `.tool-logo--fallback` |
| 3 | 切换选中工具 | 选中背景变化，logo 品牌色不变 | 通过：容器样式未覆盖 `ToolLogo` 自身 fill |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/114-provider-tool-logos (2 path rules)
[ok] 7 changed file(s), all within scope

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
709 passed, 1 warning in 23.41s

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
      Tests  83 passed (83)
   Start at  13:38:00
   Duration  9.86s


All checks passed.
```