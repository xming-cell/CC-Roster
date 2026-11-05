# 测试规则

后端 `pytest`（`backend/tests/`），前端 `vitest`（`frontend/src/__tests__/`，`*.spec.ts`）。

## 写测试的顺序
1. 先写下失败用例（描述期望行为），确认它**因为功能没写而失败**，不是因为 import 错误。
2. 再改实现，把它跑绿。
3. 最后跑 `uv run python scripts/check.py`，七道门全绿才算完成。

## 只测行为，不测实现
- 断言用户/调用方能观察到的结果：HTTP 状态码、响应体字段、渲染出来的文本。
- 前端优先 `getByRole` / `getByText` / `user-event`，**不要断言组件内部 state、私有方法、DOM 结构层级**——那是实现细节，重构就碎。
- 后端用 `TestClient` 走真实路由，别直接调 service 内部方法当「集成测试」。

## 命名与结构
- 用例名写「行为 + 条件」：`test_create_order_rejects_negative_amount`。
- 一个用例只表达一个意图；多个断言可以，但要指向同一行为。
- 共享 fixture 放 `conftest.py`，禁止在每个文件里复制同一份 setup。

## 边界必须覆盖
每个新端点/新组件至少覆盖：正常路径、缺参/非法参、边界值（0、负数、超长、空列表）、重复调用（幂等性）。

## 禁止
- 为了让测试变绿而改断言（要改就在 `PROGRESS.md` 写清理由和原断言为什么错）。
- 注释掉断言、`@pytest.mark.skip`、`.skip` / `.only` —— `scripts/guards.py` 会拦。
- mock 掉被测对象本身（等于没测）。只能 mock 外部边界：网络、时间、随机数、文件系统。