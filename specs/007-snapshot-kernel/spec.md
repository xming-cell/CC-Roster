# 007 — 快照与回滚内核

> 输入：`docs/task-plan.md` 的 007 卡；`docs/requirements.md` F-05 / N-3 / N-4 / N-11；`docs/decisions.md` ADR-003 / ADR-004 / ADR-006 / ADR-007 与附录 A / B；现有 `app/core/atomic.py`、`locks.py`、`paths.py`、`db.py`、`redaction.py` 与 006 的档案 / 绑定 / 密钥模型。
> 依赖：006 已完成（档案、模型清单、绑定、密钥存储可用）。
> 本卡只做后端「快照 + 写引擎 + 回滚 + 审计」内核：不实现 adapter `plan` / `render` / `verify` 的接线，不暴露 apply / preview 端点，不改前端；这些属于 008。007 暴露快照列表 / 详情 / pin / 回滚 API，供 008 与后续界面使用。

## 开卡决策（2026-11-11，用户确认）

1. **只做后端内核**：交付快照模型 / 内容寻址存储 / 保留策略、保真编辑助手、冲突检测、原子写引擎、快照列表 / 详情 / pin / 回滚 API、审计仓储。不实现 adapter 的 `plan` / `render` / `verify` 接线，不暴露 `POST /api/switch/*` 一类 apply / preview 端点，不改前端；008 负责消费本卡内核。
2. **TOML 使用 `tomlkit`**：JSON 用自写区间替换，TOML 用 `tomlkit` 做 round-trip 编辑，自定义 `KEY=VALUE` 格式用行编辑。新增 `tomlkit` 的理由是保留注释 / 键序 / 未知字段；同步更新 `uv.lock`，不顺带升级无关包。若 `tomlkit` 缺少类型标记，使用 mypy 模块级 override，禁止 `# type: ignore`。
3. **快照原始字节 + 严格隔离**：为满足逐字节回滚（N-3），快照 blob 保存原始字节；Unix 下 `snapshots/` 目录 `0700`、对象文件 `0600`。API、日志、diff 摘要、审计记录一律不含明文密钥，也不提供快照内容下载。ADR-006 的脱敏范围是 diff / 日志 / 审计，不是内部快照原文。
4. **外部改动观察随计划传递**：007 提供 `FileObservation` 与冲突检测内核；008 在预览读取时记录观察值，apply 时传给写引擎比对。不修改 004 的只读 `GET /api/tools`，不新增“每次读取都落库”的观察表。
5. **快照存储布局**：`<data>/snapshots/<snapshot_id>/meta.json` 存元数据，`<data>/snapshots/objects/<sha256前2位>/<sha256>` 存内容寻址分块；默认 1 MiB 一块，块大小可注入；整文件 SHA-256 与分块 SHA-256 双重校验。元数据不随 `db/` / `cache/` / `logs/` 删除，符合 ADR-007。
6. **保留策略**：按 `tool_id` 保留最近 N 份未 pin 快照，默认 N=20，`Settings.snapshot_retention` 读取 `CC_ROSTER_SNAPSHOT_RETENTION`（1–1000）。pin 的快照永不自动清理；回滚目标在回滚期间受保护，不被本次预快照触发的清理删掉。
7. **冲突与回滚语义**：冲突时拒绝覆盖、不写任何目标文件；返回结构化 `FileConflict` 详情（008 负责映射成 409 响应）。回滚是用户显式操作，不因外部改动拒绝；但回滚前必须先快照当前状态，失败时全部还原。
8. **审计落 SQLite**：新增 `audit_entries` 表（可重建，删除 `db/app.sqlite3` 后审计丢失但快照仍在）。审计只记文件 / 字段 / 快照 ID / 结果，不记明文密钥；007 只提供仓储，审计 API 留给 008 T5。
9. **多文件写入 / 回滚是全有或全无**：任一文件回读失败或写入失败，都用本次预快照还原全部目标文件；还原失败必须返回 `WRITE_RESTORE_FAILED` / `ROLLBACK_FAILED`，不得报告成功。

## 背景与目标

1. F-05 是 008「一键切换」的安全底座：任何写入前自动快照、写入后回读校验、失败自动还原、外部改动拒绝覆盖、回滚逐字节一致。
2. N-4 要求只改目标字段，注释 / 键序 / 未知字段原样保留；N-11 要求用户能看到改过哪些文件的哪些字段；N-3 要求任意一次写入都能一步回滚。
3. 006 已经有档案与绑定，但没有写入能力。007 先建立与具体工具无关的写内核，008 再把 adapter 的 `plan` / `render` / `verify` 接到本卡引擎上。

目标（按优先级）：

1. `Snapshot` 领域模型与内容寻址分块存储；保留策略、pin、损坏降级。
2. 冲突检测、原子写、回读校验、自动还原、多文件全有或全无。
3. JSON / TOML / `KEY=VALUE` 三种保真编辑助手与校验。
4. 快照列表 / 详情 / pin / 回滚 API，回滚逐字节一致。
5. 审计记录与脱敏；文档与 `check.py` 验收。

## 验收标准（DoD）

- `uv run python scripts/check.py` 退出码 0。

### 领域模型

- 新增 `app/schemas/snapshot.py`，全部 API 输入 / 输出使用 Pydantic 模型，禁止裸 `dict` / `Any`：
  - `Snapshot`：`schema_version=1`、`id`（UUID4 字符串）、`tool_id`、`profile_id`（可空）、`created_at`（带时区）、`reason`（`apply` / `rollback`）、`pinned`、`files: list[SnapshotFile]`、`changes: list[SnapshotChange]`。
  - `SnapshotFile`：`path`（绝对、规范化、已解析 symlink）、`existed`、`sha256`（不存在时为 `null`）、`size`、`mtime_ns`、`mode`（Unix 权限位；Windows 为 `null`）、`chunks: list[str]`、`chunk_size`。
  - `SnapshotChange`：`path`、`field`（展示用点分路径）、`action`（`set` / `remove`）、`before` / `after`（可空展示值，构造时经 `redact_text`，超过 200 字符截断并加 `…`）。
  - 视图：`SnapshotFileView`（不含 chunk 内容）、`SnapshotView`、`SnapshotSummary`、`SnapshotListResponse {snapshots, retention_limit, warnings}`、`SnapshotWarning {code, message}`、`SnapshotPinRequest {pinned}`、`RestoredFileView {path, action(restored/deleted/unchanged), sha256, size}`、`RollbackResponse {snapshot_id, pre_rollback_snapshot_id, files}`。
- 快照 ID 一律按 UUID4 校验，再拼文件路径；任何 `../`、绝对路径注入或非 UUID 输入都不得触达 `snapshots/` 之外。
- `SnapshotChange` 的 `before` / `after` 是调用方提供的**已脱敏展示值**；仓储 / 引擎仍会再调用一次 `redact_text`，不把原始密钥写入 `meta.json`。

### 快照存储（`app/repositories/snapshots.py`）

- 布局固定为：
  - `<data>/snapshots/<snapshot_id>/meta.json`（原子写，`write_json_atomic`）；
  - `<data>/snapshots/objects/<sha256[:2]>/<sha256>`（内容寻址块，原子写）；
  - `<data>/snapshots/.lock`（`FileLock`）。
- 文件内容按 `chunk_size` 分块（默认 1 MiB，构造函数可注入，测试用小值）；每块按 SHA-256 寻址，`SnapshotFile.chunks` 按顺序记录块 hash，整文件再算一个 SHA-256。相同块 / 相同文件跨快照只存一份。
- 空文件合法：`existed=true`、`size=0`、`sha256` 为空串的 SHA-256、`chunks=[]`；回滚后仍是空文件。
- 文件不存在也要进快照：`existed=false`、`sha256=null`、`chunks=[]`；回滚时若文件已存在则删除，恢复“本来没有这个文件”的状态。
- 捕获时从调用方传入的**同一份已校验字节**写快照，避免“冲突检查后、快照前”再次读盘产生 TOCTOU。`mtime_ns` / `mode` 取同一时刻的 stat。
- 读取 / 恢复前必须校验：meta 可解析、`schema_version` 受支持、每个 chunk 存在、拼接后整文件 SHA-256 与 `size` 匹配。任一不符 → `SNAPSHOT_UNREADABLE`（500），不写任何目标文件。
- 快照目录不存在时列表返回空、不创建目录；`snapshots/` 根不可读 / 不可写 → `SNAPSHOT_STORE_UNREADABLE` / `SNAPSHOT_WRITE_FAILED`。
- 损坏 / 未知版本的单个快照在列表里跳过并附 `SnapshotWarning`，不能让整个列表失败；详情 / 回滚遇到它返回 `SNAPSHOT_UNREADABLE`。
- 捕获 / pin / 清理在 `snapshots/.lock` 内串行化；锁超时 → `SNAPSHOT_LOCK_TIMEOUT`（503）。所有 meta 写入都是原子替换，崩溃时不产生半截 JSON。
- Unix 下创建 `snapshots/`、`objects/` 为 `0700`，对象文件与 `meta.json` 为 `0600`；Windows 依赖用户目录 ACL，不做不可靠的权限模拟。
- 孤儿对象（写 meta 失败或清理后无人引用）在下次清理时回收；回收失败只记录日志，不撤销已成功的快照或写入。

### 保留策略与 pin

- `Settings` 新增 `snapshot_retention: int`，默认 `20`，读取 `CC_ROSTER_SNAPSHOT_RETENTION`，合法范围 `1–1000`；非法值启动即报错，不静默回退。
- 保留按 `tool_id` 独立计算：每次捕获后，删除该工具最旧的、未 pin 的快照，直到数量不超过 N；`pinned=true` 的快照永不自动删除，即使总数超过 N。
- pin / unpin 幂等；修改 pin 只重写 `meta.json`，不改变 `created_at`、不复制内容块；未知快照 → 404 `SNAPSHOT_NOT_FOUND`。
- 回滚前的预快照也参与保留计算，但本次回滚的目标快照必须作为受保护 ID 跳过清理；不得出现“回滚到一半目标快照被清掉”。
- 清理删除快照目录后，扫描剩余 meta 的 chunk 引用，删除无人引用的对象文件；被其他快照引用的对象不得删除。测试覆盖“同内容两份快照，删一份后对象仍在；删两份后对象消失”。

### 外部改动检测（`FileObservation`）

- 提供 `FileObservation`：`path`、`exists`、`sha256`、`size`、`mtime_ns`；`observe_file(path)` 只读，解析 symlink 后返回绝对路径，文件缺失返回 `exists=false`。
- 写引擎在持有写锁后、快照前比对调用方传入的观察值与当前文件：
  - 观察时存在、现在不存在 → 冲突；
  - 观察时不存在、现在存在 → 冲突；
  - 两者都存在但 `sha256` 不同 → 冲突；
  - `sha256` 相同、仅 mtime 变化 → 不算冲突（内容未变），但冲突详情与审计保留实际 mtime。
- 冲突返回结构化 `FileConflict {path, reason(MISSING/CREATED/CONTENT_CHANGED), expected, actual}`，汇总为 `WriteConflict`（409，message 可读）。冲突时不创建快照、不写任何目标文件。
- 在真正替换每个文件前再做一次“当前 hash == 观察 hash”的最终检查；若外部在快照后改动，放弃该文件并走还原流程。
- 007 不把观察值写入数据库，也不修改 `GET /api/tools`；观察值由 008 的预览 / 计划携带。

### 原子写与回读校验（`app/core/atomic.py` + `app/services/write_engine.py`）

- 在 `app/core/atomic.py` 增加 `write_bytes_atomic(path, data, *, mode=None)`：同目录临时文件 → `flush` + `fsync` → `os.replace`；失败清理临时文件、原文件不变。已存在文件保留原权限位；新文件 Unix 下 `0600`。不得改变既有 `write_json_atomic` 的行为。
- 写引擎接受 `WritePlan {tool_id, profile_id, files: list[PlannedFile]}`，`PlannedFile {path, expected_bytes, observation, changes}`；所有路径必须是绝对、规范化、去 symlink 的路径，重复路径直接拒绝。
- 引擎顺序（全程持有 `<data>/locks/write.lock`，超时 `WRITE_LOCK_TIMEOUT` 503）：
  1. 读取当前文件 → 冲突检查（任一冲突则整体放弃，零写入）；
  2. 用第 1 步读到的字节生成预写入快照（含全部目标文件，缺失文件也记录）；
  3. 逐文件原子写入 `expected_bytes`；
  4. 逐文件回读，字节必须与 `expected_bytes` 完全一致；
  5. 全部通过后写审计并返回 `WriteResult {snapshot_id, audit_id, files}`。
- 回读不一致 → 用第 2 步快照还原全部已写文件（含新建文件删除），返回 `WRITE_VERIFY_FAILED`（500），详情含路径、期望 hash、实际 hash；不得报告成功。
- 任一写入 / 替换失败 → 同样还原全部文件，返回 `WRITE_FAILED`；还原本身失败 → `WRITE_RESTORE_FAILED`，详情含两边 hash。
- 快照创建失败 → 不写任何目标文件，返回 `SNAPSHOT_WRITE_FAILED`。
- 审计写入失败 → 按写入失败处理并还原，返回 `AUDIT_WRITE_FAILED`；不得出现“文件已改但无审计”的成功。
- 多文件写入顺序稳定（按路径排序）；第二个文件失败时，第一个文件必须恢复原字节。
- 引擎不负责格式化 / 渲染；`expected_bytes` 由调用方（008 的 adapter）提供。007 的格式助手单独测试。

### 保真编辑助手（`app/core/format_edits.py`）

- `DocumentFormat = json | toml | key_value`；`FieldEdit {path: list[str], action: set|remove, value: str|int|bool|None}`。`render_document(original, edits, format) -> str` 是纯函数：不读写盘、同输入同输出。
- 保真要求（用 fixture 逐字节断言）：
  - JSON：只替换 / 插入 / 删除目标值区间，其余字节（缩进、空格、换行、键序、未知字段、Unicode、转义）完全不变；不得先 `json.loads` 再 `json.dumps` 整份重排。目标键重复出现时返回 `UNSAFE_WRITE`，不猜。
  - TOML：使用 `tomlkit` round-trip；注释、空行、键序、未知表 / 键保持不变。渲染后必须再解析并校验目标字段；若库会改写目标之外的内容，必须检测并返回 `UNSAFE_WRITE`，不得静默破坏。
  - `key_value`：逐行 `KEY=VALUE` 格式，`#` 注释行与空行原样保留；已有键只替换值（保留引号风格与 `=` 两侧空格），缺失键追加到文件末尾，`remove` 删除该键所在行。重复键 → `UNSAFE_WRITE`。
- `set` 允许创建缺失的中间对象 / 表；`remove` 对不存在的键幂等（原文不变）。空路径、非字符串路径段、非法值类型 → `UNSAFE_WRITE`。
- 编码 / 换行：UTF-8（允许 BOM）与 CRLF / LF 必须原样保留；非 UTF-8、无法定位目标、解析失败、顶层不是对象 / 表 → `UNSAFE_WRITE`，不写盘。空文件按“空对象 / 空表”处理，仅当 `set` 有明确目标时生成最小合法结构。
- 提供 `verify_rendered(original, rendered, edits, format)`：重新解析渲染结果，断言每个 `set` 字段等于目标值、每个 `remove` 字段不存在；失败抛 `WRITE_VERIFY_FAILED`。渲染函数本身不写盘。

### 快照 API（`app/api/snapshots.py` + `app/services/snapshot_service.py`）

- `GET /api/snapshots?tool_id=<id>&limit=<n>`：按 `created_at` 倒序返回 `SnapshotListResponse`；`limit` 默认 50、范围 1–200；未知 `tool_id` 返回空列表；不创建目录、不写盘。
- `GET /api/snapshots/{snapshot_id}`：返回 `SnapshotView`；不存在 → 404 `SNAPSHOT_NOT_FOUND`；损坏 / 未知版本 → 500 `SNAPSHOT_UNREADABLE`；非法 UUID → 422 `VALIDATION_ERROR`。
- `PATCH /api/snapshots/{snapshot_id}`：body `{pinned: bool}`，幂等，返回 `SnapshotView`。
- `POST /api/snapshots/{snapshot_id}/rollback`：返回 `RollbackResponse`。
  - 回滚前先读取并完整校验目标快照的所有 chunk；
  - 对当前所有目标文件生成预回滚快照（`reason=rollback`，受保留保护的目标快照 ID 不被清理）；
  - 逐文件恢复：`existed=true` 写入原字节并恢复 Unix mode；`existed=false` 删除当前文件；
  - 回读校验通过后写审计并返回；失败则用预回滚快照还原全部文件，返回 `ROLLBACK_FAILED`（500）。
  - 回滚完成后目标文件与快照时**逐字节一致**（含空文件、CRLF、BOM、缺失文件）。
- 以上端点全部是同步 `def`；`api/` 只做参数绑定与转发，业务在 service，数据访问在 repository；不手写 `HTTPException`，不拼裸 dict。
- 响应只含路径、hash、大小、时间、变更摘要；**绝不返回**文件内容、chunk 内容或可直接下载的快照原文。
- 007 不暴露创建快照 / apply / preview 端点。测试通过 `WriteEngine.apply()` 或 `SnapshotService` 构造快照，再用 `TestClient` 验证 API 行为；快照创建属于 008 的 apply 流程。

### 审计（`app/repositories/audit.py` + `app/repositories/migrations.py`）

- 新增 `APP_MIGRATIONS`（v1）：`audit_entries (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, action TEXT NOT NULL, tool_id TEXT NOT NULL, profile_id TEXT, snapshot_id TEXT, files_json TEXT NOT NULL, fields_json TEXT NOT NULL, result TEXT NOT NULL, message TEXT NOT NULL)`，并为 `created_at` 建索引；`initialize_app_data` 传入该迁移。迁移幂等，旧库自动升级，删除 `db/app.sqlite3` 后重建。
- `AuditEntry` 模型与 `AuditRepository.record()` / `list_recent(limit, tool_id=None)`；`action` 为 `apply` / `rollback`，`result` 为 `success` / `failed` / `conflict`。
- 写引擎与回滚在成功 / 失败 / 冲突时记录：工具、档案、文件列表、字段列表（`path.field`）、快照 ID、结果、可读 message。`message`、文件、字段、before / after 全部经 `redact_text`；测试断言数据库文本与快照 `meta.json` 不含 fixture 明文密钥。
- 审计仓储不做业务判断；SQLite 连接使用现有 `bootstrap_database` + WAL / busy timeout，不引入 ORM。审计记录缺失 / 数据库损坏不得导致已成功的工具文件被误改；读取失败按可读错误返回。

### 文档与依赖

- `backend/pyproject.toml` 新增 `tomlkit>=0.13`，注释写明“round-trip TOML，保留注释 / 键序 / 未知字段，避免 N-4 破坏”；`backend/uv.lock` 只同步 `tomlkit` 及其必要依赖，不顺带升级无关包。不新增其他后端依赖；不新增前端依赖；不改 `pnpm-lock.yaml`。
- `README.md`：补充快照目录布局与保留策略、`CC_ROSTER_SNAPSHOT_RETENTION`、快照 API、pin / 回滚语义、原始 blob 的安全边界（含密钥可能落盘但绝不通过 API / 日志 / diff / 审计暴露、Unix 0700 / 0600、备份注意）、手动 curl 验收步骤；更新「本地数据目录」表（`snapshots/`、`audit_entries`）。
- `PROGRESS.md`：开卡决策、实现交接、下一个可执行命令。
- 手动验收（本卡无 UI / 终端 / 外部接口，用临时文件 + curl 完成）：写入前生成快照；回读不一致自动还原；外部改动被拒绝；回滚后 `cmp` / `Get-FileHash` 与原始文件逐字节一致；pin 后再次写入不清理。记录实际结果与命令输出摘要。

## 范围

```scope
backend/src/**
backend/tests/**
backend/pyproject.toml
backend/uv.lock
README.md
```

- `backend/src/**`：新增 `app/schemas/snapshot.py`、`app/repositories/snapshots.py`、`app/repositories/audit.py`、`app/repositories/migrations.py`、`app/services/snapshot_service.py`、`app/services/write_engine.py`、`app/core/format_edits.py`、`app/api/snapshots.py`；在 `app/core/atomic.py` 增加 `write_bytes_atomic`；在 `app/core/config.py` 增加 `snapshot_retention`；在 `app/core/errors.py` 增加结构化写冲突 / 写错误类型；在 `app/main.py` 挂载路由并传入 `APP_MIGRATIONS`。
- `backend/tests/**`：快照模型 / 存储 / 分块 / 保留 / pin / 损坏、观察与冲突、原子写与还原、三种格式保真、快照 API、回滚逐字节、审计脱敏；fixture 统一放 `snapshot_fixtures.py`。
- `backend/pyproject.toml`、`backend/uv.lock`：仅新增 `tomlkit` 依赖。
- `README.md`：快照存储 / 保留 / API / 安全边界 / 手动验收。
- 不改 `frontend/**`、`backend/src/app/adapters/**` 的既有行为、`GET /api/tools` 响应、`profiles.json` / `SecretStore` 行为、`docs/**`、`rules/**`、`scripts/**`、`frontend/package.json`、`frontend/pnpm-lock.yaml`。
- `PROGRESS.md`、`specs/**` 由 guard 固定放行；本卡只改本目录、`specs/CURRENT` 与交接记录。

## 边界用例（实现时必须想到）

1. 空文件、无结尾换行、BOM、CRLF、CRLF+BOM、Unicode、超长单行：快照 / 回滚逐字节一致；格式助手保留编码与换行。
2. 目标文件不存在（新文件）：快照 `existed=false`；写入失败时删除已创建文件；回滚时删除现有文件，恢复“不存在”。
3. 快照后文件被删除：回滚重新创建；父目录缺失时按记录创建，创建失败返回可读错误。
4. 分块边界：文件大小正好等于块大小、块大小 + 1、零字节、跨多块；块去重；任一 chunk 被篡改 / 删除 → `SNAPSHOT_UNREADABLE`，回滚零写入。
5. `meta.json` 坏 JSON、顶层不是对象、`schema_version` 缺失 / 大于 1、快照目录名不是 UUID：列表跳过 + warning；详情 / 回滚可读错误；不得路径穿越。
6. 快照列表 limit 越界 / 负数 / 非数字：422；未知 `tool_id`：空列表；空库：空列表且不建目录。
7. 保留：N=2 时第 3 份触发清理；最旧的 pin 后不被删；全部 pin 时允许超过 N；不同 `tool_id` 互不影响；回滚目标在预快照清理中受保护；对象在引用消失后才删除。
8. 冲突：观察后文件被改内容 / 删除 / 新建；仅 mtime 变化不冲突；两进程同时 apply 同一文件时最多一个成功，另一个得到 `WRITE_CONFLICT`，文件等于成功者的字节。
9. 写入失败：快照失败、临时文件写失败、`os.replace` 失败、回读不一致、审计失败、还原失败；每种都不得留下半截文件或假成功。
10. 多文件：第二个文件冲突 / 写入失败 / 回读失败时，第一个文件恢复原字节；新建文件被删除；还原后 hash 与快照一致。
11. 回滚多文件：第二个文件恢复失败时，第一个文件也回到预回滚状态；预回滚快照可用于再次恢复；目标快照 ID 不被清理。
12. 渲染：目标键重复、父级类型不是对象 / 表、路径不存在（remove 幂等 / set 创建父级）、非法 JSON / TOML、非 UTF-8、顶层是数组 / 标量、值含引号 / 反斜杠 / 换行 / `#`；全部要么保真成功，要么 `UNSAFE_WRITE` 且零写入。
13. 渲染确定性：同一原文 + 同一 edits 调用两次结果完全相同；render 前后源文件 hash 不变（纯函数）。
14. 快照 / 审计脱敏：fixture 明文 key 不出现在 `meta.json`、API 响应、审计表、日志、错误 message；原始 blob 允许含 key，但 API 无任何读取入口。
15. 删除 `db/app.sqlite3` / `cache/` / `logs/` 后：快照仍可列表 / 回滚，审计表自动重建（旧审计丢失），工具配置不受影响。
16. 并发：捕获 / pin / 清理与列表并发时，列表只看到完整 meta（原子写），不出现半截 JSON；锁超时返回 503。
17. Windows：文件锁、`os.replace`、权限位为 `null` 的分支可运行；Unix 权限断言只在 POSIX 执行。
18. 快照 / 回滚的路径若来自被篡改的 `meta.json`（相对路径、`..`、非绝对）：拒绝为 `SNAPSHOT_UNREADABLE`，不得写到 `snapshots/` 之外。

## 不做（明确划界）

- 不做 adapter `plan` / `render` / `verify` 接线，不实现 `POST /api/switch/preview` / `POST /api/switch/apply`（008）。
- 不做前端快照列表 / 回滚 / pin 界面（008 T7）；不改任何 `frontend/**`。
- 不做全局只读模式（016）；不拦截其他写端点。
- 不加密、不压缩快照内容；不做云同步、快照导出 / 下载、账号体系。
- 不把快照元数据放进 SQLite（按 ADR-007 留在 `snapshots/`）；审计放 SQLite。
- 不修改 004 的 `GET /api/tools`、`profiles.json`、`SecretStore` 或 006 的档案 / 绑定行为。
- 不自动合并外部改动；冲突只拒绝并返回详情。
- 不在本卡做“读取即记录观察值”的持久化；观察值由 008 的预览计划传递。
- 不新增前端依赖 / UI 库；不改 `pnpm-lock.yaml`。