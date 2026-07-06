from __future__ import annotations

import logging
import traceback
from datetime import datetime, timezone
from typing import Any

from .client import AiLoggerClient, AiLoggerClientOptions
from .levels import LogLevel
from .records import LogRecord


_STANDARD_LOG_RECORD_KEYS = frozenset(
    logging.LogRecord(
        name="standard",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="",
        args=(),
        exc_info=None,
    ).__dict__.keys()
)


class AiLoggerHttpHandler(logging.Handler):
    """Python logging handler that forwards events to an ai_logger server."""

    def __init__(
        self,
        client: AiLoggerClient | None = None,
        *,
        options: AiLoggerClientOptions | None = None,
        level: int = logging.NOTSET,
    ) -> None:
        super().__init__(level=level)
        if client is None and options is None:
            raise ValueError("Either client or options is required.")
        self.client = client or AiLoggerClient(options)  # type: ignore[arg-type]

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.client.send(log_record_from_python(record))
        except Exception:
            self.handleError(record)

    def flush(self) -> None:
        self.client.flush()

    def close(self) -> None:
        try:
            self.client.close()
        finally:
            super().close()


def log_record_from_python(record: logging.LogRecord) -> LogRecord:
    context = _context_from_python_record(record)
    exception_type = None
    exception_message = None
    stack_trace = None
    if record.exc_info:
        exc_type, exc, tb = record.exc_info
        exception_type = exc_type.__name__ if exc_type else None
        exception_message = str(exc) if exc else None
        stack_trace = "".join(traceback.format_exception(exc_type, exc, tb))

    return LogRecord(
        logger_name=record.name,
        level=_level_from_python(record.levelno),
        message=record.getMessage(),
        context=context,
        timestamp=datetime.fromtimestamp(record.created, timezone.utc),
        exception_type=exception_type,
        exception_message=exception_message,
        stack_trace=stack_trace,
    )


def _context_from_python_record(record: logging.LogRecord) -> dict[str, Any]:
    context: dict[str, Any] = {
        "module": record.module,
        "function": record.funcName,
        "line": record.lineno,
        "thread": record.threadName,
        "process": record.processName,
    }
    for key, value in record.__dict__.items():
        if key not in _STANDARD_LOG_RECORD_KEYS and not key.startswith("_"):
            context[key] = value
    return context


def _level_from_python(levelno: int) -> LogLevel:
    if levelno >= logging.CRITICAL:
        return LogLevel.CRITICAL
    if levelno >= logging.ERROR:
        return LogLevel.ERROR
    if levelno >= logging.WARNING:
        return LogLevel.WARNING
    if levelno >= logging.INFO:
        return LogLevel.INFO
    return LogLevel.DEBUG
