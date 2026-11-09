"""结构化日志: 同时写 stdout 与 `<data>/logs/app.log`, 输出前统一脱敏。

格式化器覆盖 `format()`, 因此消息正文与异常 traceback 都会经过 `redact_text`;
重复调用 `configure_logging` 不会叠加 handler 或重复输出。
"""

import logging
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePath

from app.core.paths import resolve_data_dir
from app.core.redaction import redact_text

LOG_FILE_NAME = "app.log"
_LOG_FORMAT = "%(asctime)s %(levelname)s %(name)s - %(message)s"
_HANDLER_MARKER = "_cc_roster_log_handler"


class RedactingFormatter(logging.Formatter):
    """UTC 时间戳 + 输出前脱敏。"""

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        moment = datetime.fromtimestamp(record.created, tz=UTC)
        return moment.isoformat(timespec="seconds")

    def format(self, record: logging.LogRecord) -> str:
        return redact_text(super().format(record))


def configure_logging(data_dir: PurePath | None = None, *, level: int = logging.INFO) -> None:
    """配置根 logger; `data_dir` 缺省时按 ADR-007 解析真实数据目录。"""
    root = logging.getLogger()
    if any(getattr(handler, _HANDLER_MARKER, False) for handler in root.handlers):
        return

    target_dir = Path(data_dir) if data_dir is not None else Path(resolve_data_dir())
    logs_dir = target_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    formatter = RedactingFormatter(_LOG_FORMAT)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(logs_dir / LOG_FILE_NAME, encoding="utf-8"),
    ]
    for handler in handlers:
        setattr(handler, _HANDLER_MARKER, True)
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(level)
