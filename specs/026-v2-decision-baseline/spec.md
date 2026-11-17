# 026 — V2 决策与设计基线

> 来源：`docs/task-plan2.md` §5 的 100 号卡（规划稿临时编号），正式编号 026。
> 依赖：无。后续实现卡均以本卡结论为前提。
> 性质：只写决策与设计文档，不写业务代码。

## 背景与目标
- 新信息架构以 `docs/design/01-ia.md` 为基线，但 D-9～D-17 仍待拍板，`docs/design/04-tokens.md`、`05-components.md`、`06-acceptance.md` 仍为空。
- 前端重建与后端增量都依赖同一组产品决策；如果边做边定，档案、绑定与切换的实现会返工。
- 目标：把「按新 IA 开工」所需的产品决策、视觉 token、组件状态矩阵和页面验收标准一次性定稿，并明确哪些旧功能不做。

## 验收标准（DoD）
- `uv run python scripts/check.py` 退出码 0。
- D-9～D-17 均有明确结论，写入 `docs/decisions.md`（新增 ADR 或修订 ADR-002 / ADR-003）；未确认项保留「待确认」，不得标为已完成。
- `docs/design/04-tokens.md` 包含颜色、字号、间距、圆角、阴影、动效、状态色，以及亮 / 暗模式策略。
- `docs/design/05-components.md` 包含组件清单、状态矩阵、可访问性要求；至少覆盖应用壳、导航、列表、状态徽章、详情面板、表单、确认弹窗、diff 预览、聊天气泡、输入框、空 / 错状态。
- `docs/design/06-acceptance.md` 包含页面级验收清单与手动验收场景，每项都有前置条件、操作步骤和预期结果。
- `docs/task-plan2.md` 升 v0.2：D-9～D-17 改为已接受、术语统一「供应商」、101 卡补「不做搜索框」；只同步结论，不重排工期。
- `docs/design/07-design-source.md` 说明 Penpot 源文件、快照导出与「导出代码只作标尺」的同步流程。
- `docs/design/03-hifi/` 提供快照命名规范与导出清单，定稿图可直接放入。
- `PROGRESS.md` 记录决策结论、仍未决事项与下一张可执行卡。
- 本卡不新增后端 / 前端业务代码。

## 范围

```scope
docs/decisions.md
docs/design/01-ia.md
docs/design/03-hifi/**
docs/design/04-tokens.md
docs/design/05-components.md
docs/design/06-acceptance.md
docs/design/07-design-source.md
docs/task-plan2.md
```

- `specs/**` 与 `PROGRESS.md` 由 guard 固定放行。

## 边界用例（实现时必须想到）
1. D-9 若选 B（新增 `Archive` 实体），规划中 102–105 的范围和工时必须重新评估，不能把 A 方案当成既定事实继续排期。
2. 未确认的决策只能写「待确认」；受影响的后续实现卡不得提前进入实现。
3. D-11 必须给出「工具不支持思考强度」时的行为，不能做出假选项。
4. D-15 的审计范围不得包含读取操作，也不得记录密钥、文件原文或完整请求体。
5. 组件状态矩阵必须覆盖加载、空、错误、无权限、写入中、成功、失败、部分失败，不能只写正常态。
6. 亮 / 暗模式策略必须明确是 token 层支持还是首版只做亮色；不能留成隐含假设。
7. 设计文档与 IA 冲突时，先改 ADR 并在 `PROGRESS.md` 记录原因，不能默默改 IA。

## 不做（明确划界）
- 不实现后续实现卡的任何功能，不修改后端、前端或 `scripts/`。
- 不决定具体组件库、页面视觉稿、图标库和响应式断点数值；这些留给实现卡按 tokens 落地。
- 不重写 `docs/design/01-ia.md`；如 IA 需要变更，单独记录并说明原因。
- 不删除或改写旧 `docs/task-plan.md`。
- 不把未确认决策写成「已接受」。