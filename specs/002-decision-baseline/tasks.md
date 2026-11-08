# 002 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 拍板项目名与应用 ID（CC-Roster / `com.ccroster.app`），记录到 `docs/decisions.md`，列出受影响位置：包名、窗口标题、数据目录、安装包 ID
- [x] T2 拍板「好友」粒度（一个已安装工具 = 一个好友，当前档案为属性，会话按项目目录分组），写明对 F-06 / F-08 / F-09 的影响
- [x] T3 拍板多套配置并存与全局只读模式（档案常驻应用侧，工具文件只留当前生效；只读开关放 016）
- [x] T4 拍板应用形态（P0 本地 Web，P1 加 Tauri 薄壳），画出进程边界、端口、数据目录
- [x] T5 拍板密钥存储与脱敏规则（`SecretRef` + OS keyring 优先、0600 文件回退；UI / 日志 / 错误统一脱敏）
- [x] T6 定义适配器契约：`detect / read / snapshot / plan / apply / verify / capabilities`，明确「不认识就只读降级」
- [x] T7 定义统一领域模型：`Tool / Profile / SecretRef / Snapshot / Session / Friend`，标注哪些数据可删除重建
- [x] T8 同步 README / PROGRESS / `docs/task-plan.md`，跑 `check.py` 并记录退出码

## 验收记录

命令：`uv run python scripts/check.py`　退出码：`0`（2026-11-08 20:55）

```text
=== guard scope ===

=== guard: scope ===
task card: specs/002-decision-baseline (5 path rules)
[ok] 8 changed file(s), all within scope

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
=============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  D:\我的文件夹\项目3\backend\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
1 passed, 1 warning in 0.78s

=== frontend types ===
$ vue-tsc --build

=== frontend lint ===
$ run-s "lint:*"
$ oxlint . --fix
$ eslint . --fix --cache

=== frontend tests ===
$ vitest --run

 RUN  v4.1.12 D:/我的文件夹/项目3/frontend


 Test Files  1 passed (1)
      Tests  1 passed (1)
   Start at  20:55:07
   Duration  2.97s (transform 232ms, setup 0ms, import 406ms, tests 25ms, environment 2.07s)

All checks passed.
```