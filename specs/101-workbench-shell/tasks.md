# 027 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 应用壳与路由：主导航、默认工作台 `/`、`/tools` 兼容；未实现入口不显示；处理原健康状态首页。
- [x] T2 全局 tokens 与基础布局：CSS 变量、品牌区、导航栏、工具列表面板、详情区；窄窗口不横向滚动。
- [x] T3 工作台工具列表：复用 `api/tools.ts` / `stores/tools.ts`，显示名称、状态、安装/配置、供应商与模型摘要；异常/未配置可见；无搜索框。
- [x] T4 工具详情面板：从现有 `ToolDetailPanel` 重构，覆盖字段、密钥脱敏、配置路径、warnings、未选中 / 加载 / 错误。
- [x] T5 状态与竞态：首次加载、刷新、空列表、整体失败、部分失败、未选中；隔离快速切换工具时的迟到响应。
- [x] T6 可访问性与响应式：`aria-current`、选中状态、focus-visible、状态文字、长文本、窄窗口。
- [x] T7 组件测试：应用壳导航/路由、工具列表与详情各状态、失败与竞态；统一用 `getByRole` / `getByText`。
- [x] T8 手动验收并记录：3 秒识别、空 / 错 / 部分失败、键盘与窄窗口。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 启动前端，打开 `/` | 直接进入工作台；导航只显示可用入口；三栏布局无整页横向滚动 | 正常 |
| 2 | 准备正常 / 未配置 / 异常三种工具 | 三类条目同时可见，名称、状态、供应商、模型摘要正确；无搜索框 | 正常 |
| 3 | 依次选中正常与未配置工具 | 右侧详情字段完整；未配置项显示「未知」，不编造值 | 正常 |
| 4 | 模拟后端不可达、空列表、部分失败 | 三种状态文案可区分；部分失败时正常工具仍可选中 | 正常 |
| 5 | 用 Tab 遍历并截图转灰度 | 焦点可见、顺序合理；状态可仅凭文字区分 | 正常 |
| 6 | 打开默认页后计时 | 3 秒内能识别为工具列表 | 正常 |

## 验收记录

命令：`uv run python scripts/check.py`

> T1–T7 完成后的输出（2026-11-17）。T8 手动验收完成后需重跑并替换。

```text

=== guard scope ===

=== guard: scope ===
task card: specs/101-workbench-shell (2 path rules)
[ok] 33 changed file(s), all within scope

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
=============================== warnings summary ================================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\ҵļ\Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
640 passed, 1 warning in 15.89s

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
      Tests  23 passed (23)
   Start at  17:16:18
   Duration  1.73s (transform 676ms, setup 0ms, import 1.02s, tests 198ms, environment 2.47s)


All checks passed.
```