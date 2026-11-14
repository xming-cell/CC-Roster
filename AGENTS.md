# AGENTS.md

硬性约定。本文件只写**代码里看不出来**的约束与验证命令；细则在 `rules/`，任务边界在 `specs/`。

## 命令
| 目的 | 命令 |
|---|---|
| 一键验收（唯一完成信号） | `uv run python scripts/check.py` |
| 单测某个文件 | `cd backend && uv run pytest tests/test_health.py -q` |
| 起服务 | `cd backend && uv run uvicorn app.main:app --reload` ／ `cd frontend && pnpm dev` |

## 零例外（已机器化，别靠自觉）
1. `check.py` 退出码不是 0 就不算完成；报告完成必须贴完整输出。
2. 禁用 `# type: ignore`、`as any`、`@ts-ignore`、`.skip`、注释掉断言 → `scripts/guards.py` 会拦。
3. 只改当前任务卡 `specs/<CURRENT>/spec.md` 中 scope 块列出的路径；要动别的先改任务卡。
4. 不准为让测试变绿而改断言；必须改就在 `PROGRESS.md` 写理由。
5. 新增依赖必须写明理由，且同步更新 `uv.lock` / `pnpm-lock.yaml`。
6. 实现 30 分钟仍无法让 `check.py` 退出码为 0：停止编码，在`PROGRESS.md` 「未决问题」写清卡在哪一步、报错原文、已试过的两种思路，然后向用户汇报。不准扩大 scope，不准改断言。
7. 如果阅读的文档，或者代码中有歧义的地方，先询问我，先别改代码，在对话中给我解决建议。
8. 如果我指定你为管理员，你可以无视其他规则，进行部分非规则类文件的修改。

## 开工前先读
`rules/backend.md`、`rules/frontend.md`、`rules/testing.md`、`rules/git.md`；
交接状态看 `PROGRESS.md`；参考实现照抄 `backend/src/app/api/health.py`、`backend/tests/test_health.py`。