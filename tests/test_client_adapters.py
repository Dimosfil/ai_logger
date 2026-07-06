from __future__ import annotations

import json
import logging
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger import (  # noqa: E402
    AiLoggerClient,
    AiLoggerClientOptions,
    AiLoggerHttpHandler,
    DiskJsonLinesPlugin,
    LogAggregator,
    LogRecord,
    configured_logging_handler,
    create_server,
    log_record_from_python,
)
from ai_logger.levels import LogLevel  # noqa: E402


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return b'{"accepted":1}'


class ClientAdapterTests(unittest.TestCase):
    def test_client_posts_normalized_record_with_default_context_and_redaction(self) -> None:
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse()

        client = AiLoggerClient(
            AiLoggerClientOptions(
                server_url="http://logger.example/ingest",
                token="secret-token",
                project="billing",
                service="api",
                environment="test",
                host="test-host",
            )
        )

        with patch("ai_logger.client.request.urlopen", fake_urlopen):
            delivered = client.send(
                LogRecord(
                    "app",
                    LogLevel.INFO,
                    "request.started",
                    context={"request_id": "r1", "token": "raw-secret"},
                )
            )

        self.assertTrue(delivered)
        http_request, timeout = requests[0]
        payload = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(timeout, 5.0)
        self.assertEqual(http_request.headers["Authorization"], "Bearer secret-token")
        self.assertEqual(payload["context"]["project"], "billing")
        self.assertEqual(payload["context"]["service"], "api")
        self.assertEqual(payload["context"]["environment"], "test")
        self.assertEqual(payload["context"]["host"], "test-host")
        self.assertEqual(payload["context"]["token"], "[REDACTED]")

    def test_client_writes_fallback_jsonl_when_delivery_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fallback = Path(tmp) / "fallback.jsonl"
            client = AiLoggerClient(
                AiLoggerClientOptions(
                    server_url="http://logger.example/ingest",
                    fallback_jsonl_path=fallback,
                )
            )

            with patch("ai_logger.client.request.urlopen", side_effect=OSError("down")):
                delivered = client.send(LogRecord("app", LogLevel.ERROR, "send.failed"))

            self.assertFalse(delivered)
            self.assertEqual(len(client.failed_deliveries), 1)
            payload = json.loads(fallback.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["message"], "send.failed")

    def test_python_logging_record_is_converted_to_ingest_record(self) -> None:
        logger = logging.getLogger("sample.adapter")
        record = logger.makeRecord(
            "sample.adapter",
            logging.WARNING,
            __file__,
            42,
            "job %s",
            ("slow",),
            None,
            extra={"request_id": "r1"},
        )

        converted = log_record_from_python(record)

        self.assertEqual(converted.logger_name, "sample.adapter")
        self.assertEqual(converted.level, LogLevel.WARNING)
        self.assertEqual(converted.message, "job slow")
        self.assertEqual(converted.context["request_id"], "r1")
        self.assertEqual(converted.context["line"], 42)

    def test_python_logging_handler_sends_to_ingest_server(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jsonl"
            server = create_server(
                "127.0.0.1",
                0,
                aggregator=LogAggregator([DiskJsonLinesPlugin(path)]),
                token="secret",
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                handler = AiLoggerHttpHandler(
                    options=AiLoggerClientOptions(
                        server_url=f"http://{host}:{port}/ingest",
                        token="secret",
                        project="demo",
                        service="worker",
                        environment="test",
                        host="test-host",
                    )
                )
                logger = logging.getLogger("demo.worker")
                logger.handlers = []
                logger.propagate = False
                logger.setLevel(logging.INFO)
                logger.addHandler(handler)

                logger.info("worker.started", extra={"job_id": "42"})
                handler.close()
            finally:
                server.shutdown()
                thread.join(timeout=3)
                server.server_close()

            payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["logger"], "demo.worker")
            self.assertEqual(payload["message"], "worker.started")
            self.assertEqual(payload["context"]["project"], "demo")
            self.assertEqual(payload["context"]["service"], "worker")
            self.assertEqual(payload["context"]["job_id"], "42")

    def test_configured_logging_handler_requires_server_url(self) -> None:
        with self.assertRaises(ValueError):
            configured_logging_handler(environ={})


if __name__ == "__main__":
    unittest.main()
