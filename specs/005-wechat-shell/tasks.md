# 005 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 视觉 token：新增全局样式 token（颜色 / 字号 / 间距 / 圆角 / 头像 / 气泡）并由 `main.ts` 引入；提供 `--friend-accent` / `--friend-avatar-bg` / `--bubble-*` 等覆盖点，供 011 使用；不引入 UI 库。
- [x] T2 左侧好友列表：头像位、名称、一行状态描述、四态徽章（正常 / 未配置 / 异常 / 检测中）；按 `last_modified` 降序（null / 非法排最后，同值按 `display_name` / `id`），稳定 `:key="tool.id"`，`ul` + `button`，选中态 `aria-pressed`。
- [x] T3 右侧详情 / 会话区骨架：顶部好友名称 + 状态徽章；复用 `ToolDetailPanel` 展示状态、供应商、模型、接口地址、第三方中转、脱敏密钥、最后修改时间、配置路径、warnings；未选中显示「选择一个 AI 查看详情」；预留会话时间线容器但不渲染会话。
- [x] T4 空状态与引导：无工具时显示「还没有发现任何 AI 工具」+「怎么装」入口；展开给出 Claude Code / Codex CLI 最小安装 / 配置文本（不发网络请求）；部分失败 warnings 可见。
- [x] T5 loading / 骨架 / 错误态：主界面骨架先渲染再取数；初始失败显示可读错误 + 重试；刷新失败保留旧列表 + 非阻塞提示；不出现假成功。
- [x] T6 可访问性与响应式：Tab / Enter / Space 可达、`:focus-visible` 可见、`aria-label` / `aria-pressed`；< 768px 单列且无横向滚动；组件测试用 `getByRole` / `getByText`。
- [x] T7 手动验收 + 交接：完成下方「手动验收」表；更新 README 与 PROGRESS（含 `App.spec.ts` 两条 health 断言变更理由）；跑 `check.py` 并把完整输出贴到「验收记录」。

## 手动验收

> 涉及界面与真实浏览器行为，`check.py` 不能替代人工确认。实现完成后逐项填写「实际结果」。

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 不安装任何工具，打开 `/` | 显示「还没有发现任何 AI 工具」与「怎么装」入口；展开后能看到 Claude Code / Codex CLI 指引，无控制台报错 | 正常 |
| 2 | 准备 Claude 已配置、Codex 已安装未配置两个临时目录，用 `CLAUDE_CONFIG_DIR` / `CODEX_HOME` 启动后端并打开 `/` | 两个好友同时出现，徽章不同；供应商 / 模型或「未配置」描述可读 | 正常 |
| 3 | 点击左侧好友 | 右侧显示该好友名称、状态与 004 的字段；未选中时显示「选择一个 AI 查看详情」 | 正常 |
| 4 | 把某个配置文件改坏后刷新 | 仅该好友显示「异常」；全局 warnings 与详情 warning 可见；其他好友正常 | 正常 |
| 5 | 冷启动并限制网络速度（或让 `/api/tools` 延迟返回） | 主界面骨架先出现，列表显示「检测中」；接口返回后 1 秒内可用，界面无整页空白 | 正常 |
| 6 | 停掉后端后打开 `/`，再恢复后端点「重试」 | 先显示可读错误；重试成功后恢复正常；已有列表时刷新失败不清空旧数据 | 正常 |
| 7 | 把窗口缩到约 320px / 600px，只用键盘操作 | 单列布局、无横向滚动；Tab / Enter / Space 可选好友，focus 可见 | 正常 |
| 8 | 给一位没用过该应用的人看主界面 3 秒 | 对方能说出「这是几个 AI 的列表」或等价描述 | 正常 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
=== guard scope ===

=== guard: scope ===
task card: specs/005-wechat-shell (2 path rules)
[ok] 24 changed file(s), all within scope

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
  D:\ҵļ\Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
168 passed, 1 warning in 3.65s

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
      Tests  33 passed (33)
   Start at  12:12:19
   Duration  10.06s (transform 4.64s, setup 0ms, import 7.33s, tests 1.85s, environment 27.38s)


All checks passed.
```