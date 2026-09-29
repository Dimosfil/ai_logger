from __future__ import annotations

import json
import os
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib import parse

from .aggregator import LogAggregator
from .config import build_server_aggregator_from_env
from .records import LogRecord
from .postgres_store import PostgresStore
from .telegram_bot import TelegramBot, token_from_env
from .admin import render_admin_html
from .web import WebLogRepository, render_index_html, search_levels_for_filters


class LogIngestHandler(BaseHTTPRequestHandler):
    server: "LogIngestHttpServer"

    def do_GET(self) -> None:
        path, query = self._path_and_query()
        if path.rstrip("/") in ("", "/admin") and self.server.store:
            self._send_html(HTTPStatus.OK, render_admin_html())
            return
        if path.rstrip("/") in ("", "/journal"):
            self._send_html(HTTPStatus.OK, render_index_html())
            return
        if path.rstrip("/") == "/health":
            try:
                storage_ready = not self.server.store or self.server.store.ping()
            except Exception:
                storage_ready = False
            self._send_json(
                HTTPStatus.OK if storage_ready else HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "status": "ok" if storage_ready else "storage_unavailable",
                    "service": "ai_logger",
                    "plugins": self.server.plugin_count,
                    "plugin_names": self.server.plugin_names,
                    "web": True,
                    "telegram": self.server.telegram_bot.status() if self.server.telegram_bot else {
                        "configured": False, "running": False, "error": None,
                    },
                },
            )
            return
        if path.rstrip("/") == "/api/overview":
            if self._require_scope("admin") is False:
                return
            self._send_json(HTTPStatus.OK, self.server.web_logs.overview())
            return
        if path.rstrip("/") == "/api/logs":
            if self._require_scope("admin") is False:
                return
            self._send_json(HTTPStatus.OK, self._logs_payload(query))
            return
        if path.rstrip("/") == "/api/settings":
            if self._require_scope("admin") is False:
                return
            self._send_json(HTTPStatus.OK, self.server.web_logs.settings())
            return
        if path.rstrip("/") == "/api/agent/logs" and self.server.store:
            project_scope = self._require_scope("read")
            if project_scope is False:
                return
            try:
                project = _first(query, "project")
                if project_scope and project and project != project_scope:
                    self._send_json(HTTPStatus.FORBIDDEN, {"error": "project_forbidden"})
                    return
                project = project_scope or project
                since_value = _first(query, "since")
                since = datetime.fromisoformat(since_value) if since_value else None
                if since and since.tzinfo is None:
                    raise ValueError("since needs timezone")
                records = self.server.store.read_records(
                    project=project, levels=_levels(_first(query, "levels")),
                    since=since, limit=_int_query(query, "limit", 100),
                )
            except ValueError:
                self._send_json(HTTPStatus.BAD_REQUEST, {"error": "invalid_query"})
                return
            except Exception:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "storage_unavailable"})
                return
            self._send_json(HTTPStatus.OK, {"records": records})
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})

    def do_POST(self) -> None:
        path, _query = self._path_and_query()
        if path.rstrip("/") == "/api/search":
            if self._require_scope("admin") is False:
                return
            self._handle_search()
            return
        if path.rstrip("/") == "/api/settings":
            if self._require_scope("admin") is False:
                return
            self._handle_settings()
            return
        if path.rstrip("/") != "/ingest":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "not_found"})
            return
        project_scope = self._require_scope("ingest")
        if project_scope is False:
            return

        try:
            payload = self._read_payload()
            records = payload if isinstance(payload, list) else [payload]
            if not 1 <= len(records) <= 100:
                raise ValueError("Expected 1 to 100 records")
            parsed: list[LogRecord] = []
            for item in records:
                if not isinstance(item, dict):
                    raise ValueError("Each log record must be an object.")
                record = LogRecord.from_dict(item)
                if self.server.store:
                    project = record.context.get("project")
                    if not isinstance(project, str) or not project or project != project.strip() or len(project) > 100:
                        raise ValueError("Record context.project is required")
                    if project_scope and project != project_scope:
                        self._send_json(HTTPStatus.FORBIDDEN, {"error": "project_forbidden"})
                        return
                parsed.append(record)
        except (ValueError, TypeError, AttributeError) as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        selected = [record for record in parsed if self.server.web_logs.should_collect(record)]
        if self.server.store:
            try:
                selected = self.server.store.insert_records(selected)
            except Exception:
                self._send_json(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "storage_unavailable"})
                return
        for record in selected:
            self.server.aggregator.emit(record)
        self._send_json(HTTPStatus.ACCEPTED, {"accepted": len(parsed), "stored": len(selected)})

    def log_message(self, _format: str, *_args: Any) -> None:
        if self.server.access_log:
            super().log_message(_format, *_args)

    def _authorized(self) -> bool:
        token = self.server.token
        if not token:
            return True
        return self.headers.get("Authorization") == f"Bearer {token}"

    def _require_scope(self, scope: str) -> str | bool:
        if self.server.store or scope == "admin":
            return ""
        if scope == "ingest" and self._authorized():
            return ""
        self._send_json(HTTPStatus.UNAUTHORIZED, {"error": "unauthorized"})
        return False

    def _read_payload(self) -> Any:
        length = int(self.headers.get("Content-Length") or "0")
        if length <= 0 or length > 1024 * 1024:
            raise ValueError("Request body must be 1 byte to 1 MiB")
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
            search_levels = search_levels_for_filters(levels, self.server.web_logs.enabled_levels())
            result = self.server.web_logs.search(
                query=query,
                project=_optional_str(payload.get("project")),
                file_name=_optional_str(payload.get("file")),
                levels=search_levels,
                max_records=int(payload.get("max_records") or 500),
                top_k=int(payload.get("top_k") or 8),
                use_llm=bool(payload.get("use_llm", True)),
                provider_name=_optional_str(payload.get("provider")),
                response_language=_optional_str(payload.get("response_language")) or "en",
            )
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.OK, result)

    def _handle_settings(self) -> None:
        try:
            payload = self._read_payload()
            if not isinstance(payload, dict):
                raise ValueError("Settings payload must be an object.")
            settings = self.server.web_logs.save_settings(payload)
        except Exception as exc:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return
        self._send_json(HTTPStatus.OK, settings)

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
        store: PostgresStore | None = None,
        telegram_bot: TelegramBot | None = None,
    ) -> None:
        super().__init__(server_address, LogIngestHandler)
        self.aggregator = aggregator
        self.token = token
        self.access_log = access_log
        self.web_logs = web_logs or WebLogRepository.from_env()
        self.store = store
        self.telegram_bot = telegram_bot

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
    port: int = 8766,
    *,
    aggregator: LogAggregator | None = None,
    token: str | None = None,
    access_log: bool = False,
    web_logs: WebLogRepository | None = None,
    store: PostgresStore | None = None,
    telegram_bot: TelegramBot | None = None,
) -> LogIngestHttpServer:
    return LogIngestHttpServer(
        (host, port),
        aggregator or build_server_aggregator_from_env(),
        token=token,
        access_log=access_log,
        web_logs=web_logs,
        store=store,
        telegram_bot=telegram_bot,
    )


def main() -> int:
    host, port = _bind_address_from_env(os.environ)
    token = os.environ.get("AI_LOGGER_SERVER_TOKEN")
    database_url = _database_settings_from_env(os.environ)
    store = PostgresStore(database_url, ssl=os.environ.get("DATABASE_SSL") == "1") if database_url else None
    if store:
        store.ensure_schema()
    telegram_token = token_from_env(os.environ)
    telegram_bot = TelegramBot(
        telegram_token, expected_username=os.environ.get("TELEGRAM_BOT_USERNAME")
    ) if telegram_token else None
    server = create_server(host, port, token=token, store=store, telegram_bot=telegram_bot)
    if telegram_bot:
        telegram_bot.start()
    print(f"ai_logger server listening on http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        if telegram_bot:
            telegram_bot.stop()
        server.server_close()
    return 0


def _bind_address_from_env(environ: Mapping[str, str]) -> tuple[str, int]:
    """Honor the platform's routed port while preserving local defaults."""
    platform_port = environ.get("PORT")
    host = environ.get("AI_LOGGER_SERVER_HOST") or (
        "0.0.0.0" if platform_port else "127.0.0.1"
    )
    port = int(platform_port or environ.get("AI_LOGGER_SERVER_PORT") or "8766")
    if not 1 <= port <= 65535:
        raise ValueError("Server port must be between 1 and 65535")
    return host, port


def _database_settings_from_env(environ: Mapping[str, str]) -> str | None:
    database_url = environ.get("DATABASE_URL") or None
    if environ.get("AI_LOGGER_REQUIRE_POSTGRES") == "1" and not database_url:
        raise RuntimeError("DATABASE_URL is required for hosted server")
    return database_url


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
