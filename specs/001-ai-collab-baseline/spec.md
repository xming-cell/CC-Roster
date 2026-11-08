# 001 — AI 协作基线加固

> 这是本项目第一张正式任务卡，同时作为后续所有任务卡的格式样板。
> 复制 `specs/_template/` 改名即可开新卡。

## 背景与目标

"规则写在文档里"等于没有规则：AI 读到却不遵守时，没有任何东西会失败。本卡把三条硬约定
下沉成可执行断言，并给每个需求一个可验收的规格实体，让下一个上下文窗口接手时不必猜。

目标（按优先级）：

1. `AGENTS.md` 只保留「反直觉约束 + 验证命令」，≤20 行；细则拆到 `rules/`。
2. 两条零例外规则机器化：改动范围（scope）、禁用写法（forbidden）。
3. 需求有实体：`specs/NNN-xxx/spec.md`（含验收标准与 scope）+ `tasks.md`。
4. `PROGRESS.md` 收敛为四块，专用于跨窗口交接。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0，且输出里能看到 `guard scope` 与 `guard forbidden` 两步。
- 根目录只有 `AGENTS.md`，行数 ≤ 20；细则全部在 `rules/*.md`。
- 改动 `scope` 之外的文件时，`guard scope` 必须失败并列出该文件（负例已手工验证）。
- 写入 `# type: ignore` 或 `as any` 时，`guard forbidden` 必须失败并给出 `文件:行号`（负例已手工验证）。
- `specs/CURRENT` 指向本卡时，本卡自身被完整覆盖在 scope 内（正例通过）。
- `PROGRESS.md` 为「当前状态 / 下一个可执行命令 / 已知坑 / 未决问题」四块。

## 范围

```scope
AGENTS.md
AGENT.md
PROGRESS.md
README.md  # 用户要求补齐产品介绍与开发者上手文档
docs/**  # 需求与后续任务规划文档（requirements.md / task-plan.md）
rules/**
scripts/**
specs/**
```

- `AGENT.md` 是本次 `git mv` 的旧路径，保留一行仅为让删除动作本身合法。
- `README.md` 为同卡补齐的对外说明文档，理由记录在 `PROGRESS.md`。
- `ghfetch.ps1` 已删除，不入库（见 tasks.md T8）。

## 边界用例（实现时必须想到）

1. `specs/CURRENT` 不存在或值为 `none` → 跳过范围校验，返回 0（新人第一次跑不该被卡住）。
2. `specs/CURRENT` 指向不存在的目录 → 必须失败，且提示应有的目录名格式。
3. `spec.md` 里没有 ```scope``` 块 → 必须失败，不允许"默认全放行"。
4. `scripts/guards.py` 自身的字符串常量里含有 `as any` 之类的字样 → 不许自我误伤（扫描范围只含 `backend/`、`frontend/`）。
5. 首次提交前仓库没有 `HEAD` → `guards.py` 不能崩，退化为只看暂存区 + 未跟踪文件。

## 不做（明确划界）

- 不引入 e2e / Playwright（单独开卡）。
- 不改任何业务代码、不加依赖。
- 不重构 `check.py` 的七道既有门禁，只在其前面插入两步 guard。