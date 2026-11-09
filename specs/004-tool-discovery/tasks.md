# 004 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 适配器协议 + 显式注册表：`ToolAdapter` 协议（`id` / `display_name` / `capabilities` / `managed_paths` / `detect` / `read`）与 `build_registry()`；未注册工具 / 未知结构只记 warning；`which`、`home` 可注入；共享 contract test 覆盖空目录 / 未知结构 / 权限不足 / 重复调用，并断言 `detect` / `read` 前后 fixture 目录 hash 不变。
- [x] T2 Claude Code 适配器：配置目录 `CLAUDE_CONFIG_DIR` 或 `~/.claude`，读 `settings.json` 的 `env.ANTHROPIC_BASE_URL`、`env.ANTHROPIC_AUTH_TOKEN` / `ANTHROPIC_API_KEY`、`model` / `env.ANTHROPIC_MODEL`；识别已安装 / 未配置 / 第三方中转 / 最后修改时间；不读 OAuth；fixture 覆盖已配置、未配置、坏一个字符、空文件、未知结构、权限不足。
- [x] T3 Codex CLI 适配器：配置目录 `CODEX_HOME` 或 `~/.codex`，读 `config.toml` 的 `model`、`model_provider`、`[model_providers.<id>]` 与 `auth.json` 的 `OPENAI_API_KEY`；`env_key` 只提示不读取；fixture 覆盖已配置、已安装未配置、TOML 损坏、provider 缺失、`wire_api` 未知。
- [x] T4 解析失败模型与服务隔离：`TOOL_NOT_FOUND` 之外的失败统一为 `{code, message}` warnings（`PARSE_ERROR` / `PERMISSION_DENIED` / `UNKNOWN_FORMAT` / `UNSUPPORTED_VERSION` / `CONFIG_EMPTY` / `NO_MANAGED_FIELDS` / `SECRET_IN_ENV` / `ADAPTER_ERROR`）；单适配器异常不影响其他工具；JSON / TOML 错误给出行 / 列且不回显文件内容；未知 `schema_version` 与未知 `wire_api` 降级并说明。
- [x] T5 密钥脱敏与序列化：读取密钥后立即调用 `redact_secret`；响应只给 `has_secret` + `secret_preview`；测试断言列表 / 详情 / 错误响应 / 日志的完整序列化文本都不含 fixture 明文 key（含损坏文件里带 key 的场景）。
- [x] T6 只读 API：`GET /api/tools` 返回 `{tools, warnings}`、`GET /api/tools/{tool_id}` 返回单个工具；Pydantic 响应模型、带时区 ISO 8601、同步 `def` 端点、依赖注入 service；未知 ID 404；读取前后文件 hash 与目录清单不变；TestClient 覆盖正常 / 空列表 / 部分失败 / 未知 ID / 连续调用。
- [x] T7 前端最小列表与详情：`src/api/tools.ts` 显式类型；`stores/tools.ts` 管理列表 / 选中 / loading / error / warnings；新增 `/tools` 路由与「工具」入口；列表含状态徽章（正常 / 未配置 / 异常 / 检测中）、名称、供应商、模型，详情含地址、第三方中转、脱敏密钥、最后修改时间、配置路径、warnings；空状态 / 加载态 / 失败态；组件测试用 `getByRole` / `getByText`；`/` 首页与 `App.spec.ts` 现有断言不变。
- [x] T8 验收与交接：用临时 `CLAUDE_CONFIG_DIR` / `CODEX_HOME` 完成手动验收表；README 补接口 / 页面 / 本地验收方式；PROGRESS 更新；跑 `check.py` 并把完整输出贴到本文件「验收记录」。

## 手动验收

> 涉及界面与真实文件读取，`check.py` 不能替代人工确认。实现完成后逐项填写「实际结果」。

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 准备两个临时目录：Claude 目录写入已配置 `settings.json`，Codex 目录留空；用 `CLAUDE_CONFIG_DIR` / `CODEX_HOME` 启动后端并打开 `/tools` | 同时出现 Claude（正常）与 Codex（未配置），状态不同 | 正常 |
| 2 | 把 Claude `settings.json` 改坏一个字符后刷新 `/tools` | 仅 Claude 显示异常并给出行 / 列原因；Codex 仍为未配置 | 正常 |
| 3 | 记录两个配置文件的 SHA-256，刷新列表与详情后再次比对 | hash 不变，目录下无新增临时文件 | 正常 |
| 4 | 查看列表 / 详情与浏览器网络响应 | 只出现脱敏密钥（如 `sk-a****cdef`），全文无明文 key | 正常 |
| 5 | 请求 `GET /api/tools/not-a-tool` | 返回 404 `{code: "TOOL_NOT_FOUND", message}`，无 traceback | 正常 |
| 6 | 清空两个临时目录后刷新 | 空状态与安装引导可见，页面不报错 | 正常 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/004-tool-discovery (4 path rules)
[ok] 36 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
46 files already formatted

=== backend types ===
Success: no issues found in 24 source files

=== backend tests ===
........................................................................ [ 42%]
........................................................................ [ 85%]
........................                                                 [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\我的文件夹\项目3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
168 passed, 1 warning in 2.29s

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
      Tests  15 passed (15)
   Start at  21:46:26
   Duration  4.94s (transform 1.47s, setup 0ms, import 2.76s, tests 536ms, environment 8.14s)


All checks passed.
```