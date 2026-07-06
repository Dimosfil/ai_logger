from __future__ import annotations

from typing import Any

from .aggregator import LogAggregator
from .levels import LogLevel
from .records import LogRecord


class Logger:
    def __init__(
        self,
        name: str,
        aggregator: LogAggregator,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        self.name = name
        self.aggregator = aggregator
        self.context = dict(context or {})

    def bind(self, **context: Any) -> "Logger":
        return Logger(
            self.name,
            self.aggregator,
            context={**self.context, **context},
        )

    def log(
        self,
        level: LogLevel | str | int,
        message: str,
        *,
        exc: BaseException | None = None,
        tags: tuple[str, ...] | list[str] = (),
        **context: Any,
    ) -> None:
        coerced_level = LogLevel.coerce(level)
        merged_context = {**self.context, **context}
        normalized_tags = tuple(tags)
        if exc is not None:
            record = LogRecord.from_exception(
                self.name,
                coerced_level,
                message,
                exc,
                merged_context,
                normalized_tags,
            )
        else:
            record = LogRecord(
                logger_name=self.name,
                level=coerced_level,
                message=message,
                context=merged_context,
                tags=normalized_tags,
            )
        self.aggregator.emit(record)

    def debug(self, message: str, **context: Any) -> None:
        self.log(LogLevel.DEBUG, message, **context)

    def info(self, message: str, **context: Any) -> None:
        self.log(LogLevel.INFO, message, **context)

    def warning(self, message: str, **context: Any) -> None:
        self.log(LogLevel.WARNING, message, **context)

    def error(self, message: str, **context: Any) -> None:
        self.log(LogLevel.ERROR, message, **context)

    def critical(self, message: str, **context: Any) -> None:
        self.log(LogLevel.CRITICAL, message, **context)

    def exception(
        self,
        message: str,
        exc: BaseException,
        *,
        level: LogLevel | str | int = LogLevel.ERROR,
        tags: tuple[str, ...] | list[str] = (),
        **context: Any,
    ) -> None:
        self.log(level, message, exc=exc, tags=tags, **context)
