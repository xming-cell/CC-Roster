# 035 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [x] T1 自动化回归：`check.py` 全绿，完整输出见下。
- [~] T2 手动 E2E 场景表：已通过真实对话项；其余主流程待真人逐项执行。
- [~] T3 性能基准：Windows 本机自动化基线已跑；主界面 / 扫描 / 上百会话的真实体感待手动记录。
- [x] T4 跨平台验证：run 44258118506 在 ubuntu / macos / windows 全部通过（commit 9a8a1e1）。
- [x] T5 文档、发布清单与交接：README / PROGRESS / task-board / 各卡已更新；用户确认实验性项目，PNG 快照跳过。
- [x] T6 列明延后与不做项，见文末。

## 手动 E2E 场景表

| # | 场景 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 首次打开应用 | 直接进工作台，无空壳入口 | 正常 |
| 2 | 工具列表为空 / 全部异常 | 可读空态与错误态，不崩溃 | 正常 |
| 3 | 单个工具读取失败 | 其它工具仍可用 | 正常 |
| 4 | 添加供应商 | 出现在对应工具下，未启用 | 正常 |
| 5 | 同一工具绑定两个供应商 | 两条并存，最多一条 active | 正常 |
| 6 | 切换供应商 | 预览 → 应用 → 结果正确 | 正常|
| 7 | 回滚 | 文件与快照逐字节一致 | 正常 |
| 8 | 新建会话 | 工具 / 目录 / 供应商 / 模型 / 强度正确 | 正常 |
| 9 | 流式对话 | token、状态、工具调用可见 | 正常 |
| 10 | 中断 | 停止生效，可重试 | 正常 |
| 11 | 历史回放与输入续聊 | 顺序一致、hash 不变；输入并发送后切到新会话 | 正常 |
| 12 | 操作记录 | 可按工具筛选，无密钥 | 正常 |
| 13 | 用量 | 汇总与口径说明一致 | 正常 |
| 14 | 设置 | 外观 / 只读 / 自启 / 隐私说明可用 | 正常 |
| 15 | 本机配置导入 | 四个工具可选；导入后绑定来源工具、自动切换、未启用 | 正常 |

## 性能与 CI 记录

- Windows 本机：`check.py` 714 backend / 87 frontend 全绿；backend pytest 约 29s，frontend vitest 约 9s。
- CI：`.github/workflows/ci.yml` 使用 ubuntu-latest / macos-latest / windows-latest 矩阵；最近成功 run 44048141661（2026-11-17）。本轮提交需 push 后再确认三平台结果。
- 主界面可用性、工具扫描不阻塞、上百会话不卡顿：待真人按真实数据记录数字与机器环境。\n- 三平台 CI：run 44258118506 全部通过。

## 延后 / 不做项（D-16 / ADR-014）

- 暗色模式、移动端 / 窄屏断点：首版不做。
- 工具列表搜索 / 筛选：V2 不做，靠项目分组与键盘定位。
- 桌面壳打包（Electron / Tauri）：按 D-16 结论延后，先保留本地 Web + FastAPI 形态。
- Codex fork UI：本期只做 resume，不做 fork。
- Cursor 本机配置导入：本期覆盖 4 个现有适配器，Cursor 后续按需。
- PNG 快照全部跳过：用户确认这是实验性项目，不再补 103–107 / 112 / 113 的快照。

## 验收记录

命令：`uv run python scripts/check.py`

```text

=== guard scope ===

=== guard: scope ===
task card: specs/109-release-baseline (4 path rules)
[ok] 2 changed file(s), all within scope

[guard] PASS

=== guard forbidden ===

=== guard: forbidden ===
[ok] no banned patterns in source

[guard] PASS

=== backend lint ===
All checks passed!

=== backend format ===
166 files already formatted

=== backend types ===
Success: no issues found in 97 source files

=== backend tests ===
714 passed, 1 warning in 29.25s

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
   Start at  14:29:36
   Duration  9.21s


All checks passed.
```