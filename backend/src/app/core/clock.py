"""带时区的时钟。业务代码禁止裸 `datetime.now()`。"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """返回当前 UTC 时间, 且一定带时区。"""
    return datetime.now(UTC)
