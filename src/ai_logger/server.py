from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib import parse

from .aggregator import LogAggregator
from .config import build_server_aggregator_from_env
from .records import LogRecord
from .web import WebLogRepository, render_index_html


class LogIngestHandler(BaseHTTPRequestHandler):
    server: "LogIngestHttpServer"

    def do_GET(self) -> None:
        path, query = self._path_and_query()
        if path.rstrip("/") == "":
            self._send_html(HTTPStatus.OK, render_index_html())
            return
        if path.rstrip("/") == "/health":
            self._send_json(
                HTTPStatus.OK,
                {
                    "status": "ok",
                    "service": "ai_logger",
                    "plugins": self.server.plugin_count,
                    "plugin_names": self.server.plugin_names,
                    "web": True,
                },
            )
            return
        if path.rstrip("/") == "/api/overview":
            self._send_json(HTTPStatus.OK, self.server.web_logs.overview())
            return
        if path.rstrip("/") == "/api/logs":
            self._send_json(HTTPStatus.OK, self._logs_payload(query))
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        path, _query = self._path_and_query()
        if path.rstrip("/") == "/api/search":
            self._handle_search()
            return
        if path.rstrip("/") != "/ingest":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        if not self._authorized():
            self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
            return

        try:
            payload = self._read_payload()
            records = payload if isinstance(payload, list) else [payload]
            count = 0
            for item in records:
                if not isinstance(item, dict):
                    raise ValueError("Each log record must be an object.")
                self.server.aggregator.emit(LogRecord.from_dict(item))
                count += 1
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        self._send_json(HTTPStatus.ACCEPTED, {"accepted": count})

    def log_message(self, _format: str, *_args: Any) -> None:
        if self.server.access_log:
            super().log_message(_format, *_args)

    def _authorized(self) -> bool:
        token = self.server.token
        if not token:
            return True
        return self.headers.get("Authorization") == f"Bearer {token}"

    def _read_payload(self) -> Any:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0:
            raise ValueError("Empty request body.")
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def _logs_payload(self, query: dict[str, list[str]]) -> dict[str, Any]:
        records = self.server.web_logs.read_records(
            project=_first(query, "project"),
            file_name=_first(query, "file"),
            levels=_levels(_first(query, "levels")),
            limit=_int_query(query, "limit", 200),
        )
        return {"records": [record.to_dict() for record in records]}

    def _handle_search(self) -> None:
        try:
            payload = self._read_payload()
            if not isinstance(payload, dict):
                raise ValueError("Search payload must be an object.")
            query = str(payload.get("query") or "").strip()
            if not query:
                raise ValueError("Search query is required.")
            levels_value = payload.get("levels")
            levels = {str(level).upper() for level in levels_value} if isinstance(levels_value, list) else None
            result = self.server.web_logs.search(
                query=query,
                project=_optional_str(payload.get("project")),
                file_name=_optional_str(payload.get("file")),
                levels=levels,
                max_records=int(payload.get("max_records") or 500),
                top_k=int(payload.get("top_k") or 8),
                use_llm=bool(payload.get("use_llm", True)),
                provider_name=_optional_str(payload.get("provider")),
            )
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.OK, result)

    def _path_and_query(self) -> tuple[str, dict[str, list[str]]]:
        parsed = parse.urlsplit(self.path)
        return parsed.path, parse.parse_qs(parsed.query, keep_blank_values=False)

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_html(self, status: HTTPStatus, html: str) -> None:
        data = html.encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class LogIngestHttpServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        aggregator: LogAggregator,
        *,
        token: str | None = None,
        access_log: bool = False,
        web_logs: WebLogRepository | None = None,
    ) -> None:
        super().__init__(server_address, LogIngestHandler)
        self.aggregator = aggregator
        self.token = token
        self.access_log = access_log
        self.web_logs = web_logs or WebLogRepository.from_env()

    @property
    def plugin_count(self) -> int:
        return len(getattr(self.aggregator, "_plugins", ()))

    @property
    def plugin_names(self) -> list[str]:
        return [
            str(getattr(plugin, "name", type(plugin).__name__))
            for plugin in getattr(self.aggregator, "_plugins", ())
        ]


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    aggregator: LogAggregator | None = None,
    token: str | None = None,
    access_log: bool = False,
    web_logs: WebLogRepository | None = None,
) -> LogIngestHttpServer:
    return LogIngestHttpServer(
        (host, port),
        aggregator or build_server_aggregator_from_env(),
        token=token,
        access_log=access_log,
        web_logs=web_logs,
    )


def main() -> int:
    import os

    host = os.environ.get("AI_LOGGER_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("AI_LOGGER_SERVER_PORT", "8765"))
    token = os.environ.get("AI_LOGGER_SERVER_TOKEN")
    server = create_server(host, port, token=token)
    print(f"ai_logger server listening on http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key) or []
    value = values[0].strip() if values else ""
    return value or None


def _levels(value: str | None) -> set[str] | None:
    if not value:
        return None
    levels = {part.strip().upper() for part in value.split(",") if part.strip()}
    return levels or None


def _int_query(query: dict[str, list[str]], key: str, default: int) -> int:
    value = _first(query, key)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    raise SystemExit(main())
