# 028 任务清单

状态图例：`[ ]` 待做 · `[x]` 完成并已跑过 check.py · `[~]` 做了但有前提未满足

- [ ] T1 数据完整性：`ProfileStore` 允许同一工具多条绑定，`(tool_id, profile_id)` 唯一，同一工具最多一条 `active=true`；保留档案引用校验；旧单绑定 v1 数据可直接读取。
- [ ] T2 绑定语义：`bind_tool` / `PUT /api/tools/{tool_id}/profile` 新增绑定而不删除同工具其他绑定；同供应商重复绑定幂等；未知工具 / 档案保持 404。
- [ ] T3 精确解绑：新增 `DELETE /api/tools/{tool_id}/profiles/{profile_id}`（或等价的必须指定 profile 的安全接口）；只删指定绑定，`removed=false` 幂等；解绑 active 后不自动提升其他绑定。
- [ ] T4 切换与应用：`SwitchService._save_binding` 只切换目标 binding 的 active 状态，保留其他绑定；保留 `bound_at`；A→B→A 后绑定不丢；失败 / 回滚不留下两条 active。
- [ ] T5 删除保护与查询：删除供应商检查全部绑定（含已卸载工具，`installed=false`）；`GET /api/profiles?tool_id=` 返回指定工具的绑定与供应商；未过滤时保持全量行为。
- [ ] T6 测试：多绑定、重复绑定幂等、单 active、双 active 拒绝、A→B→A、精确解绑、已卸载工具删除保护、旧 v1 数据、未知 ID、并发锁下不丢绑定。
- [ ] T7 手动验收：用 TestClient 创建 A/B 两个供应商，绑定同一工具后依次应用 A、B、A，核对绑定数量、active、bound_at、applied_at、snapshot_id；验证删除保护与精确解绑；填写下方验收表并记录 `check.py` 完整输出。

## 手动验收

| # | 操作步骤 | 预期 | 实际结果 |
|---|---|---|---|
| 1 | 创建供应商 A / B，用 `PUT /api/tools/claude-code/profile` 分别绑定到同一工具 | 返回两条不同绑定，均 `active=false`，A / B 都保留 | 待填 |
| 2 | `GET /api/profiles?tool_id=claude-code` | 只返回该工具的供应商与两条绑定 | 待填 |
| 3 | 通过现有切换 / 应用接口依次应用 A、B、A | 两条绑定始终保留；每次恰好一条 active；`bound_at` 不变，`applied_at` / `snapshot_id` 指向最后一次成功应用 | 待填 |
| 4 | `DELETE /api/tools/claude-code/profiles/{B}` | 只移除 B；A 及其状态保持不变；重复解绑返回 `removed=false` | 待填 |
| 5 | 将供应商 A 绑定到 Claude 与 Codex，再删除 A | 未确认时 409 `PROFILE_IN_USE`，`used_by` 含两个工具；确认后只清理 A 的绑定，B 不受影响 | 待填 |
| 6 | 删除工具安装目录但保留历史绑定，再删除对应供应商 | 仍返回 409，`used_by` 含 `installed=false`；确认删除不报 traceback | 待填 |
| 7 | 读取一份旧版单绑定 `profiles.json` | 列表、详情、切换均可用；文件不被主动改写；无 schema 版本错误 | 待填 |

## 验收记录

命令：`uv run python scripts/check.py`

> 待实现完成后填写完整输出；T1–T7 未完成前不算验收通过。

```text
待填
```
