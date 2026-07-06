from __future__ import annotations

import json
import socket
import threading
from pathlib import Path
from typing import Protocol
from urllib import parse
from urllib import request

from .levels import LogLevel
from .records import LogRecord


class LogPlugin(Protocol):
    name: str

    def emit(self, record: LogRecord) -> None:
        ...

    def flush(self) -> None:
        ...

    def close(self) -> None:
        ...


class BasePlugin:
    name = "base"

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.flush()


class MemoryLogPlugin(BasePlugin):
    name = "memory"

    def __init__(self) -> None:
        self.records: list[LogRecord] = []
        self._lock = threading.Lock()

    def emit(self, record: LogRecord) -> None:
        with self._lock:
            self.records.append(record)


class DiskJsonLinesPlugin(BasePlugin):
    name = "disk_jsonl"

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()

    def emit(self, record: LogRecord) -> None:
        line = json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(line)
                stream.write("\n")


class HttpJsonPlugin(BasePlugin):
    name = "http_json"

    def __init__(
        self,
        url: str,
        *,
        timeout_seconds: float = 5.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            **(headers or {}),
        }

    def emit(self, record: LogRecord) -> None:
        payload = json.dumps(record.to_dict(), ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            self.url,
            data=payload,
            headers=self.headers,
            method="POST",
        )
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            response.read()


class ServerHttpPlugin(HttpJsonPlugin):
    name = "server_http"

    def __init__(
        self,
        url: str,
        *,
        token: str | None = None,
        timeout_seconds: float = 5.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        plugin_headers = dict(headers or {})
        if token:
            plugin_headers["Authorization"] = f"Bearer {token}"
        super().__init__(
            url,
            timeout_seconds=timeout_seconds,
            headers=plugin_headers,
        )


class GraylogGelfPlugin(BasePlugin):
    name = "graylog_gelf"

    _level_map = {
        LogLevel.DEBUG: 7,
        LogLevel.INFO: 6,
        LogLevel.WARNING: 4,
        LogLevel.ERROR: 3,
        LogLevel.CRITICAL: 2,
    }

    def __init__(
        self,
        url: str,
        *,
        host: str | None = None,
        timeout_seconds: float = 5.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.host = host or socket.gethostname()
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            **(headers or {}),
        }

    def emit(self, record: LogRecord) -> None:
        payload = self._to_gelf(record)
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            self.url,
            data=data,
            headers=self.headers,
            method="POST",
        )
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            response.read()

    def _to_gelf(self, record: LogRecord) -> dict[str, object]:
        context = dict(record.context)
        full_message = record.stack_trace or record.exception_message or record.message
        payload: dict[str, object] = {
            "version": "1.1",
            "host": str(context.pop("host", self.host)),
            "short_message": record.message,
            "full_message": full_message,
            "timestamp": record.timestamp.timestamp(),
            "level": self._level_map.get(record.level, 6),
            "_logger": record.logger_name,
            "_record_id": record.record_id,
        }
        if record.tags:
            payload["_tags"] = ",".join(record.tags)
        if record.exception_type:
            payload["_exception_type"] = record.exception_type
            payload["_exception_message"] = record.exception_message or ""
        for key, value in context.items():
            safe_key = "".join(ch if ch.isalnum() or ch == "_" else "_" for ch in str(key))
            payload[f"_{safe_key}"] = value
        return payload


class ClickHouseHttpPlugin(BasePlugin):
    name = "clickhouse_http"

    def __init__(
        self,
        url: str,
        *,
        table: str,
        timeout_seconds: float = 5.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.url = url
        self.table = table
        self.timeout_seconds = timeout_seconds
        self.headers = {
            "Content-Type": "application/json; charset=utf-8",
            **(headers or {}),
        }

    def emit(self, record: LogRecord) -> None:
        query = parse.urlencode({"query": f"INSERT INTO {self.table} FORMAT JSONEachRow"})
        separator = "&" if "?" in self.url else "?"
        target = f"{self.url}{separator}{query}"
        payload = json.dumps(record.to_dict(), ensure_ascii=False).encode("utf-8") + b"\n"
        http_request = request.Request(
            target,
            data=payload,
            headers=self.headers,
            method="POST",
        )
        with request.urlopen(http_request, timeout=self.timeout_seconds) as response:
            response.read()
