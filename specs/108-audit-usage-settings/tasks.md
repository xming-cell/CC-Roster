# 034 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 设计：Penpot 出稿「操作记录 / 用量 / 设置」三张画板与空错态，导出快照，**停下来等用户确认**。
- [x] T2 前端：audit API 模块与操作记录页（时间、动作、工具、供应商、结果、快照入口、工具筛选）。
- [x] T3 前端：usage API 模块与用量页（汇总、明细、未知价格、口径说明）。
- [x] T4 前端：设置页与外观覆盖。
- [x] T5 前端：只读、快捷键、开机自启的能力探测与降级。
- [x] T6 前端：隐私 / 本地数据说明。
- [x] T7 组件测试与手动验收并记录 `check.py` 输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 打开操作记录并按工具筛选 | 时间倒序、筛选生效、无密钥泄露 | 通过：本地页面实测 + `AuditView.spec.ts` |
| 2 | 从一条 apply 记录进入快照 | 能到达对应快照 / 失败时说明不可用 | 通过：`AuditView.spec.ts` 模拟快照详情；缺失提示不可用 |
| 3 | 打开用量页 | 次数、token、花费与口径说明一致；未知价格标未知 | 通过：本地页面实测 + `UsageView.spec.ts`（含全未知价格） |
| 4 | 切换外观偏好并刷新 | 偏好保持，失败时回滚提示 | 通过：`SettingsView.spec.ts` 校验保存与失败回滚 |
| 5 | 开启只读模式后尝试写操作 | 写入口禁用并说明原因 | 通过：设置页与供应商页只读组件测试 |
| 6 | 在不支持自启 / 快捷键的平台查看设置 | 隐藏或明确标注不可用 | 通过：`SettingsView.spec.ts` 平台能力降级 |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/108-audit-usage-settings (3 path rules)
[ok] 38 changed file(s), all within scope

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
687 passed, 1 warning in 22.80s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  14 passed (14)
      Tests  76 passed (76)
   Start at  22:55:49
   Duration  5.09s (transform 8.61s, setup 0ms, import 14.51s, tests 2.80s, environment 31.15s)


All checks passed.
```
