# 036 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [ ] T1 后端：TOML 解析与版本校验（`schema_version = 1`，`[[profiles]]`），错误可读。
- [ ] T2 后端：Codex 配置读取（CODEX_HOME / ~/.codex），provider → 候选，密钥字段转存。
- [ ] T3 后端：复用去重 / skip-overwrite / 全或无 / `profile_import` 审计，补测试。
- [ ] T4 设计：导入对话框增加「从 Codex 配置读取」，导出快照并等用户确认。
- [ ] T5 前端：TOML 文件选择 + Codex 配置入口 + 预览展示。
- [ ] T6 组件与手动验收，回填 `check.py` 输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 导入一份合法 TOML | 预览分类正确，确认后写入 | 待填 |
| 2 | 从本机 Codex 配置读取 | 预览 provider 与模型，密钥只显示有无 | 待填 |
| 3 | 导入带 token 的配置 | 供应商可健康检查，审计无明文 | 待填 |
| 4 | 未知版本 / 坏 TOML | 可读错误，整批不写 | 待填 |

## 验收记录

命令：`uv run python scripts/check.py`

```text
待填
```
