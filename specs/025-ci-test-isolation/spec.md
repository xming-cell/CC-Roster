# 025 — 隔离跨平台测试的应用数据目录

## 背景与目标
- CI 的 `macos-latest` 变红：settings 测试把 `read_only=true` 写进真实用户数据目录，污染后续快照测试。
- 根因：测试只用 `LOCALAPPDATA` 隔离，而 `resolve_data_dir()` 在 macOS 读 `HOME`、Linux 读 `XDG_DATA_HOME`。
- 目标：所有后端测试在 Windows / macOS / Linux 都只读写自己的临时数据目录，不再依赖运行平台。

## 验收标准（DoD）
- `uv run python scripts/check.py` 退出码 0。
- `backend/tests/conftest.py` 提供 autouse fixture，把 `LOCALAPPDATA`、`XDG_DATA_HOME`、`HOME` 同时指向当前测试的 `tmp_path`。
- `test_settings_api.py` 不再硬编码 `tmp_path / "CC-Roster"`，改为从 `resolve_data_dir()` 推导 settings 路径。
- 同一测试进程内先开启只读、再运行快照回滚测试时，后者仍返回 200，不出现 `READ_ONLY_MODE`。

## 范围

```scope
backend/tests/**
```

## 边界用例（实现时必须想到）
1. 测试自己覆盖 `LOCALAPPDATA` 时，settings 路径仍必须与实际数据目录一致。
2. 不读写文件系统的测试也会获得独立临时目录，不能因共享状态互相影响。
3. Windows 分支继续用 `LOCALAPPDATA`；macOS / Linux 分支分别由 `HOME` / `XDG_DATA_HOME` 覆盖。

## 不做（明确划界）
- 不改生产代码、不改 CI workflow。
- 不改任何测试断言，不删除既有用例。
- 不引入新的 pytest 插件或环境变量开关。