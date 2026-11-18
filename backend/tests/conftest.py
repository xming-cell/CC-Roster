"""全局测试隔离: 每个测试使用独立的应用数据目录。

`resolve_data_dir` 在不同平台读取不同的环境变量: Windows 用 `LOCALAPPDATA`,
macOS 用 `HOME`, Linux 用 `XDG_DATA_HOME`。只隔离 `LOCALAPPDATA` 会让 macOS /
Linux 的测试读写真实用户目录, 把只读开关之类的状态泄漏给后续测试。
"""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_app_data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把三平台的数据目录环境变量都指向当前测试的临时目录。"""
    data_root = tmp_path / "app-data"
    monkeypatch.setenv("LOCALAPPDATA", str(data_root))
    monkeypatch.setenv("XDG_DATA_HOME", str(data_root))
    monkeypatch.setenv("HOME", str(data_root))
    return data_root
