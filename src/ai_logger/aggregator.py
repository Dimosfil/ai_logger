from __future__ import annotations

import sys
import threading
from collections import deque
from typing import Callable, Iterable

from .levels import LogLevel
from .plugins import LogPlugin
from .records import LogRecord

LogFilter = Callable[[LogRecord], bool]


class LogAggregator:
    def __init__(
        self,
        plugins: Iterable[LogPlugin] | None = None,
        *,
        min_level: LogLevel | str | int = LogLevel.DEBUG,
        default_context: dict[str, object] | None = None,
        max_failed_records: int = 1000,
        error_stream=None,
    ) -> None:
        self.min_level = LogLevel.coerce(min_level)
        self.default_context = dict(default_context or {})
        self.max_failed_records = max_failed_records
        self.error_stream = error_stream or sys.stderr
        self._plugins: list[LogPlugin] = list(plugins or [])
        self._filters: list[LogFilter] = []
        self._failed_records: deque[tuple[LogRecord, str, str]] = deque(
            maxlen=max_failed_records
        )
        self._lock = threading.RLock()

    @property
    def failed_records(self) -> tuple[tuple[LogRecord, str, str], ...]:
        with self._lock:
            return tuple(self._failed_records)

    def add_plugin(self, plugin: LogPlugin) -> None:
        with self._lock:
            self._plugins.append(plugin)

    def add_filter(self, log_filter: LogFilter) -> None:
        with self._lock:
            self._filters.append(log_filter)

    def emit(self, record: LogRecord) -> None:
        if record.level < self.min_level:
            return

        enriched = self._enrich(record)
        with self._lock:
            if any(not log_filter(enriched) for log_filter in self._filters):
                return
            plugins = tuple(self._plugins)

        for plugin in plugins:
            try:
                plugin.emit(enriched)
            except Exception as exc:  # pragma: no cover - defensive fallback path.
                self._remember_delivery_failure(enriched, plugin.name, exc)

    def flush(self) -> None:
        with self._lock:
            plugins = tuple(self._plugins)
        for plugin in plugins:
            try:
                plugin.flush()
            except Exception as exc:  # pragma: no cover - defensive fallback path.
                self._remember_delivery_failure(
                    LogRecord("ai_logger", LogLevel.ERROR, "logger.flush_failed"),
                    plugin.name,
                    exc,
                )

    def close(self) -> None:
        with self._lock:
            plugins = tuple(self._plugins)
        for plugin in plugins:
            try:
                plugin.close()
            except Exception as exc:  # pragma: no cover - defensive fallback path.
                self._remember_delivery_failure(
                    LogRecord("ai_logger", LogLevel.ERROR, "logger.close_failed"),
                    plugin.name,
                    exc,
                )

    def _enrich(self, record: LogRecord) -> LogRecord:
        if not self.default_context:
            return record
        context = {**self.default_context, **record.context}
        return LogRecord(
            logger_name=record.logger_name,
            level=record.level,
            message=record.message,
            context=context,
            tags=record.tags,
            timestamp=record.timestamp,
            record_id=record.record_id,
            exception_type=record.exception_type,
            exception_message=record.exception_message,
            stack_trace=record.stack_trace,
        )

    def _remember_delivery_failure(
        self,
        record: LogRecord,
        plugin_name: str,
        exc: BaseException,
    ) -> None:
        with self._lock:
            self._failed_records.append((record, plugin_name, str(exc)))
        print(
            f"ai_logger delivery failure in plugin={plugin_name}: {exc}",
            file=self.error_stream,
        )
