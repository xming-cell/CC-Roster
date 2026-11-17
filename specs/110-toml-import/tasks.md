# 036 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 后端：TOML 解析与版本校验（`schema_version = 1`，`[[profiles]]`），错误可读。
- [x] T2 后端：Codex 配置读取（CODEX_HOME / ~/.codex），provider → 候选，密钥字段转存。
- [x] T3 后端：复用去重 / skip-overwrite / 全或无 / `profile_import` 审计，补测试。
- [x] T4 设计：导入对话框增加「从 Codex 配置读取」，导出快照并等用户确认。
- [x] T5 前端：TOML 文件选择 + Codex 配置入口 + 预览展示。
- [x] T6 组件与手动验收，回填 `check.py` 输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 导入一份合法 TOML | 预览分类正确，确认后写入 | 通过：`test_profile_import_toml.py` + 导入对话框测试 |
| 2 | 从本机 Codex 配置读取 | 预览 provider 与模型，密钥只显示有无 | 通过：本机真实预览返回 OpenAI / `has_secret=true` |
| 3 | 导入带 token 的配置 | 供应商可健康检查，审计无明文 | 通过：后端测试校验密钥库与审计无明文 |
| 4 | 未知版本 / 坏 TOML | 可读错误，整批不写 | 通过：未知版本 / 坏 TOML / 空 provider 测试 |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/110-toml-import (5 path rules)
[ok] 18 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
160 files already formatted

=== backend types ===
Success: no issues found in 94 source files

=== backend tests ===
........................................................................ [ 10%]
........................................................................ [ 20%]
........................................................................ [ 31%]
........................................................................ [ 41%]
........................................................................ [ 51%]
........................................................................ [ 62%]
........................................................................ [ 72%]
........................................................................ [ 82%]
........................................................................ [ 93%]
................................................                         [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\�ҵ��ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
696 passed, 1 warning in 22.76s

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
      Tests  78 passed (78)
   Start at  23:19:54
   Duration  5.29s (transform 9.52s, setup 0ms, import 15.72s, tests 3.28s, environment 30.23s)


All checks passed.
```
