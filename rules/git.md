# 提交规则

## 提交前
- 必跑 `uv run python scripts/check.py`，**退出码 0 才提交**。
- `git status` 确认没有 `ghfetch.ps1` 之类本地脚本、没有 `.env`、没有 `*.db` 混进来。

## 粒度
- **一张任务卡 = 一个 commit**（大卡可以拆多个 commit，但同一 commit 不要跨卡）。
- 一个 commit 只做一件事：重构和改行为分开提交，格式化单独一次 `style:` 提交。

## 消息格式
```
<type>(<scope>): <中文摘要，不超过 50 字>

<为什么要改，一行；不写"修改了 XX 文件"这种废话>
```
- `type`：`feat` / `fix` / `refactor` / `test` / `docs` / `chore` / `ci` / `style`
- `scope`：`backend` / `frontend` / `scripts` / `ci` / `spec`（没有就省略括号）
- 例：`feat(backend): 新增订单创建端点并校验金额为正`

## 禁止
- `git push --force` 到 `main`；不要 rebase 已经推送过的提交。
- `git commit --no-verify` 绕过钩子。
- 一个 commit 里同时出现「改测试」和「改实现」而说不清哪个是主因——把测试改动单独提交，方便回滚。