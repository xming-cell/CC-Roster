# 010 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

## 前置检查

- [x] 开工前重读 `rules/backend.md`、`rules/frontend.md`、`rules/testing.md`、`rules/git.md`、`PROGRESS.md`；确认 005 已完成且 `specs/CURRENT` 指向本卡。
- [x] 检查工作区状态；009 已提交并推送，开卡只包含本卡文件、当前指针与交接。

## 任务

- [x] T1 后端筛选契约：为 `GET /api/tools` 增加可选名称 / 供应商 / 模型 / 状态参数；覆盖缺省、空值、大小写、非法状态与组合筛选。
- [x] T2 内存过滤与规模验证：服务层实现纯内存过滤，不新增索引；用 120+ 个合成工具验证结果、原顺序与过滤性能。
- [x] T3 主界面搜索与状态筛选：增加搜索框、状态 chips、200ms 防抖、即时状态反馈、结果数量及无匹配文案 / 清除入口；组件测试覆盖键盘操作和空态。
- [x] T4 状态与排序回归：搜索 / 状态组合不改变 005 排序、工具原始列表、选中 ID 或详情；连续输入只呈现最新条件；测试筛出所选工具及恢复筛选。
- [x] T5 文档与收尾：README 更新主界面与 API 参数说明；`uv run python scripts/check.py` 退出码 0，完整输出贴入验收记录。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 在主界面输入名称、供应商或模型片段 | 停止输入后 200ms 更新匹配列表；不重新请求工具列表 | 待验收 |
| 2 | 在搜索结果上切换正常 / 未配置 / 异常状态，再清除状态 | 搜索与状态组合正确；清除后恢复原列表及排序 | 待验收 |
| 3 | 选中一个工具后筛选到不匹配，再清空筛选 | 详情持续显示，工具恢复后仍为选中项 | 待验收 |
| 4 | 输入无匹配关键词并使用清除入口 | 显示「没有匹配项」及清除入口；清除后恢复列表 | 待验收 |
| 5 | 直接访问 `/tools` 并查看其列表 | 过渡页面行为不变 | 待验收 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/010-search-filter (9 path rules)
[ok] 6 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
93 files already formatted

=== backend types ===
Success: no issues found in 49 source files

=== backend tests ===
........................................................................ [ 12%]
........................................................................ [ 25%]
........................................................................ [ 38%]
........................................................................ [ 51%]
........................................................................ [ 64%]
........................................................................ [ 77%]
........................................................................ [ 90%]
....................................................                     [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\�ҵ��ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
556 passed, 1 warning in 32.01s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend

 Test Files  9 passed (9)
      Tests  85 passed (85)
   Start at  23:05:23
   Duration  12.36s (import 20.47s, tests 5.64s, environment 51.22s)


All checks passed.
```
