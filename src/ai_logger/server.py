from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from .aggregator import LogAggregator
from .config import build_server_aggregator_from_env
from .records import LogRecord


class LogIngestHandler(BaseHTTPRequestHandler):
    server: "LogIngestHttpServer"

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/ingest":
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

    def _send_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(int(status))
        self.send_header("Content-Type", "application/json; charset=utf-8")
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
    ) -> None:
        super().__init__(server_address, LogIngestHandler)
        self.aggregator = aggregator
        self.token = token
        self.access_log = access_log


def create_server(
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    aggregator: LogAggregator | None = None,
    token: str | None = None,
    access_log: bool = False,
) -> LogIngestHttpServer:
    return LogIngestHttpServer(
        (host, port),
        aggregator or build_server_aggregator_from_env(),
        token=token,
        access_log=access_log,
    )


def main() -> int:
    import os

    host = os.environ.get("AI_LOGGER_SERVER_HOST", "127.0.0.1")
    port = int(os.environ.get("AI_LOGGER_SERVER_PORT", "8765"))
    token = os.environ.get("AI_LOGGER_SERVER_TOKEN")
    server = create_server(host, port, token=token)
    print(f"ai_logger server listening on http://{host}:{port}/ingest")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        return 0
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
