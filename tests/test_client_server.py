from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger import (  # noqa: E402
    ClickHouseHttpPlugin,
    DiskJsonLinesPlugin,
    GraylogGelfPlugin,
    LogAggregator,
    Logger,
    ServerHttpPlugin,
    create_server,
)


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return b""


class ClientServerTests(unittest.TestCase):
    def test_client_plugin_sends_records_to_ingest_server(self) -> None:
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
                client_logger = Logger(
                    "client",
                    LogAggregator(
                        [
                            ServerHttpPlugin(
                                f"http://{host}:{port}/ingest",
                                token="secret",
                            )
                        ]
                    ),
                )

                client_logger.error("job.failed", job_id="42")
            finally:
                server.shutdown()
                thread.join(timeout=3)
                server.server_close()

            payload = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["logger"], "client")
            self.assertEqual(payload["message"], "job.failed")
            self.assertEqual(payload["context"]["job_id"], "42")

    def test_graylog_plugin_converts_record_to_gelf(self) -> None:
        plugin = GraylogGelfPlugin("http://graylog.example/gelf", host="test-host")
        logger = Logger("worker", LogAggregator([plugin]))
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse()

        with patch("ai_logger.plugins.request.urlopen", fake_urlopen):
            logger.warning("worker.slow", service="api", request_id="r1")

        request, timeout = requests[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(timeout, 5.0)
        self.assertEqual(payload["version"], "1.1")
        self.assertEqual(payload["host"], "test-host")
        self.assertEqual(payload["short_message"], "worker.slow")
        self.assertEqual(payload["_service"], "api")
        self.assertEqual(payload["_request_id"], "r1")

    def test_clickhouse_plugin_uses_json_each_row_insert(self) -> None:
        plugin = ClickHouseHttpPlugin("http://clickhouse.example:8123", table="logs")
        logger = Logger("worker", LogAggregator([plugin]))
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse()

        with patch("ai_logger.plugins.request.urlopen", fake_urlopen):
            logger.info("worker.started")

        request, _timeout = requests[0]
        self.assertIn("INSERT+INTO+logs+FORMAT+JSONEachRow", request.full_url)
        payload = json.loads(request.data.decode("utf-8"))
        self.assertEqual(payload["logger"], "worker")
        self.assertEqual(payload["message"], "worker.started")


if __name__ == "__main__":
    unittest.main()
