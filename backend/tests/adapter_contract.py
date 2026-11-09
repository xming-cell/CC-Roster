"""适配器只读契约测试的共享骨架。

T2 / T3 的适配器测试继承 `AdapterContract`, 提供 `make_adapter` 与三个
fixture 种子方法即可复用同一组行为断言。本文件不被 pytest 收集。
"""

import hashlib
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from app.adapters.base import ToolAdapter


def snapshot_tree(root: Path) -> dict[str, str]:
    """目录清单 + 文件内容 hash, 用于断言 detect/read 前后没有任何变化。"""
    entries: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root).as_posix()
        if path.is_dir():
            entries[relative] = "<dir>"
        else:
            entries[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return entries


def assert_read_only[T](root: Path, action: Callable[[], T]) -> T:
    """执行一次读取并断言 fixture 目录的清单与内容 hash 不变。"""
    before = snapshot_tree(root)
    result = action()
    assert snapshot_tree(root) == before
    return result


@contextmanager
def deny_reads(paths: tuple[Path, ...]) -> Iterator[None]:
    """把目标文件的 `Path.open` 替换为 PermissionError, 模拟权限不足。

    适配器必须通过 pathlib 读取配置文件 (`read_text` / `read_bytes` / `open`),
    否则这里拦不到。这是契约的一部分, 也避免测试真的去改文件权限。
    """
    targets = set(paths)
    original_open = Path.open

    def guarded_open(self: Path, *args: object, **kwargs: object) -> object:
        if self in targets:
            raise PermissionError(f"permission denied: {self}")
        return original_open(self, *args, **kwargs)

    with patch.object(Path, "open", guarded_open):
        yield


class AdapterContract:
    """只读契约: 空目录 / 未知结构 / 权限不足 / 重复调用 / 不写盘。"""

    def make_adapter(self, config_dir: Path) -> ToolAdapter:
        raise NotImplementedError

    def seed_configured(self, config_dir: Path) -> None:
        raise NotImplementedError

    def seed_unknown_structure(self, config_dir: Path) -> None:
        raise NotImplementedError

    def test_empty_config_dir_is_installed_but_unconfigured(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        adapter = self.make_adapter(config_dir)

        detection = assert_read_only(config_dir, adapter.detect)
        repeated = assert_read_only(config_dir, adapter.detect)

        assert detection.installed is True
        assert detection.configured is False
        assert repeated == detection

    def test_unknown_structure_only_produces_warnings(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        self.seed_unknown_structure(config_dir)
        adapter = self.make_adapter(config_dir)

        detection = assert_read_only(config_dir, adapter.detect)
        result = assert_read_only(config_dir, adapter.read)
        repeated_detection = assert_read_only(config_dir, adapter.detect)
        repeated_result = assert_read_only(config_dir, adapter.read)

        assert detection.configured is False
        assert detection.warnings or result.warnings
        assert repeated_detection == detection
        assert repeated_result == result

    def test_configured_fixture_is_read_only_and_repeatable(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        self.seed_configured(config_dir)
        adapter = self.make_adapter(config_dir)

        detection = assert_read_only(config_dir, adapter.detect)
        result = assert_read_only(config_dir, adapter.read)
        repeated_detection = assert_read_only(config_dir, adapter.detect)
        repeated_result = assert_read_only(config_dir, adapter.read)

        assert detection.installed is True
        assert detection.configured is True
        assert detection.warnings == []
        assert result.warnings == []
        assert repeated_detection == detection
        assert repeated_result == result

    def test_permission_denied_is_a_warning_not_an_exception(self, tmp_path: Path) -> None:
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        self.seed_configured(config_dir)
        adapter = self.make_adapter(config_dir)
        before = snapshot_tree(config_dir)

        with deny_reads(adapter.managed_paths):
            detection = adapter.detect()
            result = adapter.read()

        assert snapshot_tree(config_dir) == before
        warnings = [*detection.warnings, *result.warnings]
        assert any(warning.code == "PERMISSION_DENIED" for warning in warnings)
