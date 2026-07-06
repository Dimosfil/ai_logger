from __future__ import annotations

import json
import socket
import threading
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping
from urllib import request

from .records import LogRecord


DEFAULT_REDACT_KEYS = frozenset(
    {
        "api_key",
        "apikey",
        "authorization",
        "cookie",
        "password",
        "private_key",
        "secret",
        "set_cookie",
        "token",
    }
)


@dataclass(frozen=True)
class AiLoggerClientOptions:
    server_url: str
    token: str | None = None
    project: str | None = None
    service: str | None = None
    environment: str | None = None
    host: str | None = None
    timeout_seconds: float = 5.0
    fallback_jsonl_path: str | Path | None = None
    redact_keys: frozenset[str] = field(default_factory=lambda: DEFAULT_REDACT_KEYS)


class AiLoggerClient:
    """Framework-neutral client for the ai_logger ingest protocol."""

    def __init__(self, options: AiLoggerClientOptions) -> None:
        self.options = options
        self.failed_deliveries: deque[str] = deque(maxlen=1000)
        self._lock = threading.RLock()

    def send(self, record: LogRecord | Mapping[str, Any]) -> bool:
        return self.send_many([record])

    def send_many(self, records: Iterable[LogRecord | Mapping[str, Any]]) -> bool:
        payload = [self._normalize_record(record) for record in records]
        if not payload:
            return True
        body: dict[str, Any] | list[dict[str, Any]]
        body = payload[0] if len(payload) == 1 else payload
        try:
            self._post(body)
        except Exception as exc:  # pragma: no cover - concrete failures are tested via behavior.
            self._remember_failure(exc)
            self._write_fallback(payload)
            return False
        return True

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.flush()

    def _normalize_record(self, record: LogRecord | Mapping[str, Any]) -> dict[str, Any]:
        payload = record.to_dict() if isinstance(record, LogRecord) else dict(record)
        context = dict(payload.get("context") or {})
        context = {
            **self._default_context(),
            **context,
        }
        payload["context"] = redact_value(context, self.options.redact_keys)
        if "exception" in payload:
            payload["exception"] = redact_value(payload["exception"], self.options.redact_keys)
        return json_safe(redact_value(payload, self.options.redact_keys))

    def _default_context(self) -> dict[str, Any]:
        context: dict[str, Any] = {}
        if self.options.project:
            context["project"] = self.options.project
        if self.options.service:
            context["service"] = self.options.service
        if self.options.environment:
            context["environment"] = self.options.environment
        context["host"] = self.options.host or socket.gethostname()
        return context

    def _post(self, payload: dict[str, Any] | list[dict[str, Any]]) -> None:
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if self.options.token:
            headers["Authorization"] = f"Bearer {self.options.token}"
        data = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        http_request = request.Request(
            self.options.server_url,
            data=data,
            headers=headers,
            method="POST",
        )
        with request.urlopen(http_request, timeout=self.options.timeout_seconds) as response:
            response.read()

    def _remember_failure(self, exc: BaseException) -> None:
        with self._lock:
            self.failed_deliveries.append(str(exc))

    def _write_fallback(self, records: list[dict[str, Any]]) -> None:
        if not self.options.fallback_jsonl_path:
            return
        path = Path(self.options.fallback_jsonl_path)
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as stream:
                for record in records:
                    stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
                    stream.write("\n")


def json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(item) for item in value]
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return str(value)


def redact_value(value: Any, redact_keys: frozenset[str] = DEFAULT_REDACT_KEYS) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in redact_keys:
                redacted[key_text] = "[REDACTED]"
            else:
                redacted[key_text] = redact_value(item, redact_keys)
        return redacted
    if isinstance(value, (list, tuple, set)):
        return [redact_value(item, redact_keys) for item in value]
    return value
