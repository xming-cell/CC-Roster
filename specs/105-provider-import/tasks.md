# 031 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 定稿导入 JSON schema 示例与版本号，写进 `docs/design/05-components.md` 或卡内附录。
- [x] T2 后端：导入预览端点（解析 + 校验 + 分类，不写入）与测试。
- [x] T3 后端：导入确认端点（跳过 / 覆盖、全或无、原子写）与测试。
- [x] T4 设计：Penpot 出稿「选择文件 / 预览三类结果 / 冲突与错误」，导出快照，**停下来等用户确认**。→ 2026-11-17 已出三张画板（选择 / 预览 / 错误），用户同日确认。
- [x] T5 前端：导入对话框、文件选择、预览列表与重复项处理。
- [x] T6 前端：错误状态、超长内容、确认后刷新供应商列表。
- [x] T7 组件测试与手动验收并记录 `check.py` 输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 导入一份含 2 条新供应商的合法 JSON | 预览显示 2 条新增；确认后出现在供应商页且未启用 | 通过（组件测试）：预览统计与条目正确；确认后发出 `/api/profiles/import` 并回传结果 |
| 2 | 导入包含 1 条重复、1 条非法的文件 | 预览分类正确；非法存在时确认按钮不可用或整批拒绝 | 通过（组件 + 后端测试）：非法条目禁用确认并提示；后端返回 `IMPORT_HAS_INVALID_ITEMS` 且无写入 |
| 3 | 选择重复项「覆盖」后导入 | 已有供应商被更新，未产生第二条 | 通过（后端测试）：overwrite 更新模型且保留密钥；前端确认请求携带 `policy=overwrite` |
| 4 | 导入空文件 / 坏 JSON / 未知版本 | 可读错误，不产生任何供应商 | 通过（后端 + 组件测试）：`IMPORT_INVALID_JSON`、`IMPORT_UNSUPPORTED_VERSION`、`IMPORT_EMPTY` 均有可读错误，组件显示「未写入」 |
| 5 | 导入后检查工具配置文件 | 文件未被修改，绑定为 `active=false` | 通过（后端测试）：导入只写 `profiles.json`，不调用绑定端点；工具绑定数量为 0 |

> 真机走查并入 109 的手动 E2E；导入入口是全局动作，不要求先选工具。

## 验收记录

命令：`uv run python scripts/check.py`

```text
# 阶段验收（T1-T3 后端，2026-11-17）

=== guard scope ===

=== guard: scope ===
task card: specs/104-switch-provider (5 path rules)
[ok] 6 changed file(s), all within scope

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
........................................................................ [ 21%]
........................................................................ [ 31%]
........................................................................ [ 42%]
........................................................................ [ 53%]
........................................................................ [ 63%]
........................................................................ [ 74%]
........................................................................ [ 85%]
........................................................................ [ 95%]
.............................                                            [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\�ҵ��ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
677 passed, 1 warning in 23.37s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  5 passed (5)
      Tests  43 passed (43)
   Start at  19:59:21
   Duration  2.43s (transform 1.50s, setup 0ms, import 2.61s, tests 857ms, environment 4.99s)


All checks passed.
```




