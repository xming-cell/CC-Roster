# AGENTS.md

本文件是硬性约定，违反即打回。不要修改本文件，除非任务明确要求。

## 结构
- `backend/` FastAPI · Python 3.12 · uv 管理依赖
- `frontend/` Vue 3 · Vite · TS · pnpm 管理依赖

## 命令
| 目的 | 命令 |
|---|---|
| 一键验收（提交前必跑） | `uv run python scripts/check.py` |
| 后端单测 | `cd backend && uv run pytest -q` |
| 单测某个文件 | `cd backend && uv run pytest tests/test_health.py -q` |
| 前端单测 | `cd frontend && pnpm test:unit --run` |
| 起后端 | `cd backend && uv run uvicorn app.main:app --reload` |
| 起前端 | `cd frontend && pnpm dev` |

## 硬性规则
1. 报告"完成"必须附 `scripts/check.py` 的完整输出。**没有退出码 0 就不算完成**。
2. 禁止改测试断言来让测试变绿。测试挂了先修实现；真要改测试，先在 PROGRESS.md 写理由。
3. 禁止 `# type: ignore`、`as any`、`@ts-ignore`、`.skip`、注释掉断言。
4. 禁止改任务卡「允许改动」范围外的文件。
5. 新增依赖必须写明理由。

## 代码约定
- 后端分层：`api/`（路由，只做参数校验+转发）→ `services/`（业务）→ `repositories/`（数据访问）。
  **路由里不写业务逻辑，service 里不写 SQL。**
- 所有 API 输入输出必须是 Pydantic 模型，禁止裸 `dict`。
- 金额一律 `Decimal`，禁止 `float`。
- 错误统一抛 `AppError`，由全局 handler 转成 `{code, message}`。
- 前端所有 HTTP 请求走 `src/api/`，组件内禁止直接 `fetch`。
- 复用优先：后端先看 `app/core/`，前端先看 `src/utils/`。

## 参考实现（照抄风格）
- 端点：`backend/src/app/api/health.py`
- 测试：`backend/tests/test_health.py`