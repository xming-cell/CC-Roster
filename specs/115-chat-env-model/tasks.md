# 041 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 复现：真实对话报 `unrecognized_model` 与 `SystemRoot` 缺失。
- [x] T2 失败测试：父环境 `SystemRoot` 保留、Claude 不传 `--model`、终端 spawner 继承环境。
- [x] T3 修复：统一环境合并并在 Windows 同时补齐 `SYSTEMROOT` / `SystemRoot`。
- [x] T4 修复：Claude 使用 `ANTHROPIC_MODEL`；会话模型切换同步进入 env；Codex `--model` 不变。
- [x] T5 完整验收并回填；真实模型对话复测待用户执行。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 用 DeepSeek / 第三方 Anthropic 兼容模型发消息 | 不再报 `unrecognized_model` | 待用户真实复测 |
| 2 | 同上，观察 Windows 子进程 | 不再报 `SystemRoot` 缺失 | 待用户真实复测 |
| 3 | 切换会话模型 | 后续消息使用新模型 | 通过：env `ANTHROPIC_MODEL` 测试 |
| 4 | Codex 对话 | 仍通过 `--model` 选择模型 | 通过：现有命令测试 |

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/115-chat-env-model (3 path rules)
[ok] 9 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
167 files already formatted

=== backend types ===
Success: no issues found in 98 source files

=== backend tests ===
717 passed, 1 warning in 19.76s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend

 Test Files  15 passed (15)
      Tests  87 passed (87)
   Start at  14:53:20
   Duration  7.66s


All checks passed.
```