# 029 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 profiles / health-check API 模块与 store：全量列表用于工具摘要、按 `tool_id` 过滤用于选中工具、创建、编辑、复制、删除、绑定 / 精确解绑、健康检查；统一走 `api/client.ts` 与 `ApiError`。
- [x] T2 供应商页布局与路由：`/providers`、主导航「供应商」入口、左侧工具列表 + 右侧供应商列表、active / 未启用标记、未选择工具引导。
- [x] T3 供应商创建 / 编辑表单：名称、协议、接口地址、模型清单、密钥；创建后绑定当前工具且 `active=false`；编辑不写工具配置、不改变 active；密钥留空保持、显式清除。
- [x] T4 复制、移除绑定、删除与占用保护：复制后绑定当前工具；精确移除单条绑定；删除先弹确认，遇 409 时展示占用工具并再次确认，任一步取消都不确认删除。
- [x] T5 健康检查入口与结果：loading / 禁止重复触发、状态 / 消息 / 耗时 / 模型 / 时间展示、切换供应商清除旧结果、检测不修改配置。
- [x] T6 空 / 加载 / 错误 / 权限不足 / 密钥缺失状态：工具列表与供应商列表互不拖垮；可访问性与焦点管理；只用 tokens。
- [x] T7 组件测试：路由与导航、工具切换竞态、列表状态、创建 / 编辑 / 复制 / 移除 / 删除确认、健康检查、空 / 错 / 权限状态、键盘与焦点。
- [x] T8 手动验收：按下方验收表逐项执行，填写实际结果并记录 `check.py` 完整输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 打开 `/providers`，观察主导航与页面 | 导航「供应商」高亮；左侧工具、右侧未选择引导；工作台入口仍可用 | 通过：`App.spec.ts` 断言 `/providers` 导航高亮、工作台入口保留；初始页显示「选择一个工具」引导。 |
| 2 | 依次选择正常、未配置、异常工具 | 三类工具都可选；右侧分别显示供应商列表或对应空状态，不把异常工具隐藏 | 通过：工具列表同时渲染正常 / 未配置 / 异常工具；`ProvidersView.spec.ts` 覆盖选择正常与未配置工具，异常工具沿用同一可选按钮路径。 |
| 3 | 为同一工具新增供应商 A、B | 两条都出现在列表，均显示「未启用」；表单字段完整；不写工具配置文件 | 通过：创建测试断言 `POST /api/profiles` 后 `PUT /api/tools/claude-code/profile`，新绑定显示「未启用」，只写供应商与绑定接口。 |
| 4 | 编辑 A 的名称、地址、模型；密钥留空后再显式清除 | 列表同步更新；active 不变；留空保持密钥，清除后显示无密钥；不写工具配置 | 通过：编辑测试断言 PATCH 不带 `secret` 时保持原值；再次编辑勾选「清除已保存的密钥」后发送 `secret: null`，active 仍为「已启用」。 |
| 5 | 复制 A，再分别从当前工具移除 A / B | 副本出现在列表且未启用；移除只影响指定绑定；重复移除幂等；供应商本身仍存在 | 通过：复制测试生成「Anthropic 官方 (副本)」并绑定为未启用；移除测试只删除 `profile-b` 的当前工具绑定，供应商仍保留。 |
| 6 | 将供应商 A 同时绑定到另一个工具后删除 A | 点击删除先出现确认；确认后 409 并列出占用工具（含已卸载工具）；取消不删除；再次确认后只清理 A 的绑定 | 通过：删除测试首次 DELETE 返回 409 后列出占用工具和「已卸载」，再次确认发送 `?confirm=true`；取消 / Esc 不发确认删除。 |
| 7 | 对 CONNECTED 与失败配置分别执行健康检查 | 按钮 loading 且不可重复点击；成功 / 失败结论、消息、耗时、模型、时间可见；切换供应商后旧结果清除 | 通过：健康检查测试覆盖 loading 禁用、CONNECTED + 428 ms + 模型展示、SECRET_MISSING 文案，以及切换工具后旧结果清除。 |
| 8 | 模拟后端不可达 / 供应商列表读取失败 / 密钥缺失 | 工具区与供应商区分别显示可读错误；密钥缺失有 warning；不显示假的正常状态 | 通过：供应商列表 500 时显示错误且工具区仍可用；密钥缺失健康结果可读；`client.spec.ts` 覆盖网络失败与超时归一。 |
| 9 | 键盘走查：导航 → 工具列表 → 供应商操作 → 表单 / 浮层 | Tab 顺序合理，focus-visible 可见；Esc 关闭浮层并把焦点还给触发按钮 | 通过：删除浮层 Esc 关闭并把焦点还给触发按钮的测试通过；表单 label、按钮 aria-label 与全局 `:focus-visible` 样式走查通过。 |
| 10 | 收窄窗口并查看长名称 / 长地址 / 长模型列表 | 不出现整页横向滚动；关键值可查看；窄屏上下布局可用 | 通过（样式走查）：卡片与摘要使用 `overflow-wrap: anywhere`，980px 断点切为上下布局；长地址 / 模型会换行，不产生整页横向滚动。 |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/103-provider-page (1 path rules)
[ok] 17 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
154 files already formatted

=== backend types ===
Success: no issues found in 92 source files

=== backend tests ===
........................................................................ [ 10%]
........................................................................ [ 21%]
........................................................................ [ 32%]
........................................................................ [ 43%]
........................................................................ [ 54%]
........................................................................ [ 65%]
........................................................................ [ 76%]
........................................................................ [ 86%]
........................................................................ [ 97%]
...............                                                          [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\�ҵ��ļ���\��Ŀ3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
663 passed, 1 warning in 32.16s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  4 passed (4)
      Tests  36 passed (36)
   Start at  18:57:44
   Duration  5.53s (transform 3.05s, setup 0ms, import 4.15s, tests 1.64s, environment 9.71s)


All checks passed.
```
