# 011 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

## 前置检查

- [x] 开工前重读 `rules/backend.md`、`rules/frontend.md`、`rules/testing.md`、`rules/git.md`、`PROGRESS.md`；确认 005、010 已完成且 `specs/CURRENT` 指向本卡。
- [x] 检查工作区状态；不覆盖或回退其他未提交改动。

## 任务

- [x] T1 默认外观推导：实现按工具 ID 稳定的身份主色、按供应商 / 模型生成次级强调色与默认背景 / 气泡预设；未知值有确定性兜底。覆盖 5+ 工具 ID、重复计算 / 列表重排稳定性和明 / 暗对比度。
- [x] T2 外观覆盖存储与 API：新增版本化 `appearances.json` repository、原子读写 / 文件锁、Pydantic schema、读取 / 保存 / 恢复默认 API；覆盖缺失、损坏、未知版本、非法输入、并发、写失败与零配置副作用。
- [x] T3 好友外观应用：将默认 / 已保存外观应用到好友头像、列表项、当前详情与时间线预留区；验证档案切换、工具排序 / 筛选、选中状态不串色；明 / 暗与窄屏行为通过组件测试。
- [x] T4 手动覆盖与恢复默认：提供按工具的强调色 / 背景色编辑和气泡预设选择；保存失败明确报错，恢复只重置当前工具；覆盖、刷新持久化、失败 / 取消、键盘操作均有行为测试。
- [x] T5 文档与收尾：README 说明默认外观、编辑 / 恢复及可重建存储；完成 5+ 好友的视觉区分手动验收与回归记录；`uv run python scripts/check.py` 退出码 0，完整输出贴入验收记录。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 在五个或以上不同工具 ID 的好友列表中遮住 / 不读名称观察视觉身份 | 主色和次级样式足以区分；文字、状态和焦点仍清晰 | 正常 |
| 2 | 为一个好友更改强调色、聊天背景和气泡预设后刷新页面 | 只有该好友外观变化；刷新后覆盖保留，列表 / 详情一致 | 正常 |
| 3 | 对已覆盖好友使用「恢复默认」，并重启应用 | 该好友恢复稳定默认外观，其他好友覆盖不变 | 正常 |
| 4 | 在好友列表使用搜索 / 状态筛选并切换选中项 | 外观跟随工具 ID，不串色；筛除后清除条件可恢复原项外观 | 正常 |
| 5 | 使用键盘完成编辑 / 取消 / 恢复，并在 320px 和系统明 / 暗偏好下查看 | 控件可达、焦点可见、无横向溢出，所有文本和按钮对比清晰 | 正常 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/011-friend-appearance (4 path rules)
[ok] 23 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
98 files already formatted

=== backend types ===
Success: no issues found in 53 source files

=== backend tests ===
........................................................................ [ 12%]
........................................................................ [ 25%]
........................................................................ [ 37%]
........................................................................ [ 50%]
........................................................................ [ 63%]
........................................................................ [ 75%]
........................................................................ [ 88%]
..................................................................       [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\�ҵ�ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
570 passed, 1 warning in 20.35s

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
      Tests  92 passed (92)
   Start at  14:40:45
   Duration  7.51s (transform 4.17s, setup 0ms, import 8.71s, tests 2.91s, environment 41.72s)


All checks passed.
```
