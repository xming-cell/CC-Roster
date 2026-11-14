"""原子 JSON 写: 同目录临时文件 + `os.replace`。

写入失败时原文件保持不变, 临时文件被清理。
"""

import json
import os
import stat
import tempfile
from pathlib import Path


def write_json_atomic(path: Path, data: object) -> None:
    """把 `data` 序列化为 JSON 并原子替换 `path`。"""
    payload = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def write_bytes_atomic(path: Path, data: bytes, *, mode: int | None = None) -> None:
    """把 `data` 原子替换到 `path`。

    `mode` 省略时保留已存在文件的权限位; 新文件默认 `0600`。写入失败时原文件
    保持不变, 临时文件被清理。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if mode is None:
        try:
            mode = stat.S_IMODE(path.stat().st_mode)
        except FileNotFoundError:
            mode = 0o600

    fd, temp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temp_path, mode)
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
