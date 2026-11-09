# 003 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 `AppError` + 全局异常处理器：`{code, message}`；业务异常 / Pydantic 校验 / 404 / 405 / 未知异常；未知异常返回 500 且不含 traceback、路径、密钥；`create_app()` 工厂便于测试挂载测试路由；pytest 覆盖已知 / 未知异常。
- [x] T2 时钟与数据目录：`utc_now()` 返回带时区 datetime；`resolve_data_dir()` 按 ADR-007 覆盖 Windows / macOS / Linux；目录创建幂等；`settings` 补 `app_name="CC-Roster"`、`host="127.0.0.1"`、CORS 白名单、请求体上限；测试用 `PureWindowsPath` / `PurePosixPath`。
- [x] T3 存储基础设施：SQLite bootstrap（WAL、busy timeout、`PRAGMA user_version`、可注入迁移列表、幂等）；删除 `db/app.sqlite3` 后可重建；`user_version` 超前明确报错；原子 JSON 写与跨平台文件锁（带超时）；测试覆盖失败保留原文件、锁超时。
- [x] T4 本地安全边界：默认仅监听 `127.0.0.1`；CORS 只放行 `http://localhost:5173` / `http://127.0.0.1:5173`；请求体上限 1 MiB，超限返回 413 `PAYLOAD_TOO_LARGE`；测试非白名单无 ACAO、超限 413。
- [x] T5 日志与脱敏：结构化日志写 stdout + `<data>/logs/`；`redact_secret()` 按 ADR-006 三档规则；`redact_text()` 覆盖 `sk-...` / `Bearer ...`；日志格式化器在输出前脱敏；假 key 断言日志与异常响应均无明文。
- [x] T6 前端请求层：`src/api/client.ts`（显式类型、超时、`ApiError` 归一）+ `src/api/health.ts`；组件禁止直接 `fetch`；Vitest 覆盖成功 / HTTP 错误 / 网络错误 / 超时。
- [x] T7 前端路由、Pinia 与应用壳：`router` 增加 `/` 首页；`stores/app.ts` 管理后端状态；`App.vue` 提供壳布局与 `<RouterView />`，首页保留 `backend: ok`；清理脚手架 `stores/counter.ts`；组件测试。
- [x] T8 文档与验收：README 补数据目录 / loopback / 日志 / 启动说明；PROGRESS 交接更新；跑 `check.py` 并把完整输出贴到本文件「验收记录」。

## 手动验收

> 涉及界面与本地服务启动，`check.py` 不能替代人工确认。实现完成后逐项填写「实际结果」。

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 启动后端 `uv run uvicorn app.main:app --reload` | 仅绑定 `127.0.0.1:8000`；`<data>/db` 与 `<data>/logs` 被创建 | 正常 |
| 2 | 启动前端 `pnpm dev` 并打开 `http://localhost:5173` | 首页显示 `backend: ok`，无控制台错误 | 正常 |
| 3 | 停止服务，删除 `db/app.sqlite3` 后重启 | 数据库自动重建，首页仍正常 | 待填 |
| 4 | 浏览器访问不存在的 `/api/does-not-exist` | 返回 `{code, message}`，无 `detail`、无 traceback | 待填 |
| 5 | 查看 `<data>/logs/` 最新日志 | 时间、级别、消息可读；无明文假 key | 待填 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/003-local-infra (6 path rules)
[ok] 38 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
26 files already formatted

=== backend types ===
Success: no issues found in 14 source files

=== backend tests ===
.................................................................        [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\ҵļ\Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
65 passed, 1 warning in 1.40s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  2 passed (2)
      Tests  7 passed (7)
   Start at  19:33:22
   Duration  3.07s (transform 436ms, setup 0ms, import 628ms, tests 155ms, environment 3.83s)


All checks passed.
```

退出码：0