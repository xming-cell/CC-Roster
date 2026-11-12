# 009 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

## 前置检查

- [x] 开工前重读 `rules/backend.md`、`rules/frontend.md`、`rules/testing.md`、`rules/git.md`、`PROGRESS.md`；确认 `specs/CURRENT` 指向本卡。
- [x] 检查工作区状态并记录 `uv run python scripts/check.py` 基线；不得覆盖或回退其他未提交改动。

## 任务

- [x] T1 后端契约与请求边界：新增体检请求 / 响应 schema 和稳定结果码；按协议、档案模型与 SecretStore 构造一次最小探测；超时有上限、禁用重定向、无自动重试；网络传输可注入测试边界。
- [x] T2 结果分类与服务：实现成功、认证失败、地址错误、模型不存在、超时、限流、密钥不可用、未知失败分类；上游响应和异常转换为脱敏的人话说明，不回传原始正文。
- [x] T3 用户主动触发 API：新增 `POST /api/profiles/{profile_id}/health-check`，未知档案 404、模型参数校验清晰；不写档案 / 工具配置，不创建快照 / 审计 / 历史；覆盖 API 集成与零副作用。
- [x] T4 安全与边界测试：覆盖合法 / 非法模型、空模型清单、正确与错误凭证、错地址、超时、429、异常上游响应、重复请求；断言响应 / 日志 / 异常中无完整假 key，磁盘和数据库状态不变。
- [x] T5 前端档案体检：在 `/profiles` 每份档案提供模型选择和体检按钮；默认首个模型，空清单时禁用并说明；显示可能产生少量费用的提示、loading、耗时、结论和重试；覆盖键盘操作、窄屏、并发点击与失败状态。
- [x] T6 README、手动验收与收尾：README 和交接已更新，完整验收输出已记录；真实地址 / 错地址 / 错 key / 不存在模型四种供应商请求未执行，尚未获得用户选择的档案 / 模型与明确请求授权。

## 手动验收

> 使用用户明确选择的档案和模型；每次体检会向该档案地址发起真实请求，可能产生少量费用。记录供应商 / 模型与结论，不记录密钥。

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 用正确地址、有效凭证及可用模型主动体检 | 显示连通、耗时和可读成功说明 | 未执行：待用户选择档案 / 模型并授权真实请求 |
| 2 | 把档案地址临时设为不可达地址并体检 | 显示地址错误；不回显原始异常 | 未执行：待用户选择档案 / 模型并授权真实请求 |
| 3 | 临时使用无效 key 并体检 | 显示密钥无效；响应 / 日志不含 key | 未执行：待用户选择档案 / 模型并授权真实请求 |
| 4 | 选择档案清单中不存在于上游的模型并体检 | 显示模型不存在，与其他失败结论不同 | 未执行：待用户选择档案 / 模型并授权真实请求 |
| 5 | 记录体检前后档案、工具配置、快照与审计状态 | 所有配置与持久化数据不变；未点击前无请求 | 自动化副作用测试通过；真实数据目录前后核对未执行 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/009-health-check (7 path rules)
[ok] 14 changed file(s), all within scope

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
........................................................................ [ 13%]
........................................................................ [ 26%]
........................................................................ [ 39%]
........................................................................ [ 52%]
........................................................................ [ 65%]
........................................................................ [ 78%]
........................................................................ [ 91%]
................................................                         [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\�ҵ��ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
552 passed, 1 warning in 41.56s

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
      Tests  84 passed (84)
   Start at 21:17:20
   Duration 13.51s (transform 9.94s, setup 0ms, import 18.98s, tests 5.49s, environment 68.80s)

All checks passed.
```
