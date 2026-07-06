from __future__ import annotations

import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from types import TracebackType
from typing import Any, Mapping
from uuid import uuid4

from .levels import LogLevel


Context = Mapping[str, Any]


@dataclass(frozen=True)
class LogRecord:
    logger_name: str
    level: LogLevel
    message: str
    context: dict[str, Any] = field(default_factory=dict)
    tags: tuple[str, ...] = ()
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    record_id: str = field(default_factory=lambda: uuid4().hex)
    exception_type: str | None = None
    exception_message: str | None = None
    stack_trace: str | None = None

    @classmethod
    def from_exception(
        cls,
        logger_name: str,
        level: LogLevel,
        message: str,
        exc: BaseException,
        context: Context | None = None,
        tags: tuple[str, ...] = (),
        traceback_obj: TracebackType | None = None,
    ) -> "LogRecord":
        tb = traceback_obj if traceback_obj is not None else exc.__traceback__
        return cls(
            logger_name=logger_name,
            level=level,
            message=message,
            context=dict(context or {}),
            tags=tags,
            exception_type=type(exc).__name__,
            exception_message=str(exc),
            stack_trace="".join(traceback.format_exception(type(exc), exc, tb)),
        )

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.record_id,
            "timestamp": self.timestamp.isoformat(),
            "logger": self.logger_name,
            "level": self.level.name,
            "level_value": int(self.level),
            "message": self.message,
            "context": dict(self.context),
            "tags": list(self.tags),
        }
        if self.exception_type:
            data["exception"] = {
                "type": self.exception_type,
                "message": self.exception_message,
                "stack_trace": self.stack_trace,
            }
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "LogRecord":
        exception = data.get("exception") or {}
        timestamp_value = str(data.get("timestamp") or "")
        try:
            timestamp = datetime.fromisoformat(timestamp_value)
        except ValueError:
            timestamp = datetime.now(timezone.utc)
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return cls(
            logger_name=str(data.get("logger") or data.get("logger_name") or "unknown"),
            level=LogLevel.coerce(data.get("level_value") or data.get("level") or LogLevel.INFO),
            message=str(data.get("message") or ""),
            context=dict(data.get("context") or {}),
            tags=tuple(str(tag) for tag in data.get("tags") or ()),
            timestamp=timestamp,
            record_id=str(data.get("id") or data.get("record_id") or uuid4().hex),
            exception_type=exception.get("type"),
            exception_message=exception.get("message"),
            stack_trace=exception.get("stack_trace"),
        )
