# 001 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 `git mv AGENT.md AGENTS.md`，正文压到 20 行内，只留反直觉约束 + 验证命令
- [x] T2 拆出 `rules/backend.md`、`rules/frontend.md`、`rules/testing.md`、`rules/git.md`
- [x] T3 新增 `scripts/guards.py`：`scope`（越界改动）+ `forbidden`（禁用写法）
- [x] T4 `scripts/check.py` 前置两步 guard，秒级失败
- [x] T5 `specs/` 骨架：`CURRENT` 指针 + 本卡 + `_template/`
- [x] T6 `PROGRESS.md` 改为四块交接结构
- [x] T7 修掉 `guards.py` 两个实现缺陷：无 `HEAD` 的仓库会崩、BOM/中文导致 `UnicodeEncodeError`
- [x] T8 决定 `ghfetch.ps1` 去留：T8 删除 ghfetch.ps1（未入库）
- [ ] T9 下一个业务需求开 `specs/002-*/`，把 `specs/CURRENT` 改成 `002`

## 验收记录

命令：`uv run python scripts/check.py`　退出码：`0`（2026-11-04 22:11）

```text
=== guard scope ===

=== guard: scope ===
task card: specs/001-ai-collab-baseline (7 path rules)
[ok] 15 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
5 files already formatted

=== backend types ===
Success: no issues found in 4 source files

=== backend tests ===
.                                                                        [100%]
1 passed, 1 warning in 0.53s

=== frontend types ===
(无输出即通过)

=== frontend lint ===
Found 0 warnings and 0 errors.
Finished in 38ms on 9 files with 144 rules using 16 threads.

=== frontend tests ===
 RUN  v4.1.12 D:/我的文件夹/项目3/frontend
 ✓ src/__tests__/App.spec.ts (1 test) 16ms
 Test Files  1 passed (1)
      Tests  1 passed (1)

All checks passed.
```

### 负例验证（手动跑过，证明门禁真的会拦）

| 场景 | 命令 | 期望 | 实测 |
|---|---|---|---|
| 改动范围外的新文件 | `guards.py scope` | 列出 2 个越界文件并退出 1 | ✅ 通过 |
| 源码写入 `as any` / `it.skip` | `guards.py forbidden` | 报 `文件:行号` 并退出 1 | ✅ 通过 |
| `specs/CURRENT` 为 `none` | `guards.py scope` | 跳过校验、退出 0 | ✅ 通过 |
| `specs/CURRENT` 指向不存在的目录 | `guards.py scope` | 报错并退出 1 | ✅ 通过 |
| `spec.md` 缺 ```scope``` 块 | `guards.py scope` | 报错并退出 1，不默认放行 | ✅ 通过 |
| 带 BOM + 中文的源文件 | `guards.py forbidden` | 正常输出，不抛 UnicodeEncodeError | ✅ 通过 |