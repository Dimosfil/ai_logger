from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib import request

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
from ai_logger.web import WebLogRepository  # noqa: E402


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return b""


class ClientServerTests(unittest.TestCase):
    def test_ingest_server_health_endpoint_reports_ready(self) -> None:
        server = create_server(
            "127.0.0.1",
            0,
            aggregator=LogAggregator([DiskJsonLinesPlugin(Path(tempfile.gettempdir()) / "unused.jsonl")]),
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            with request.urlopen(f"http://{host}:{port}/health", timeout=5) as response:
                payload = json.loads(response.read().decode("utf-8"))
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["service"], "ai_logger")
        self.assertEqual(payload["plugins"], 1)
        self.assertEqual(payload["plugin_names"], ["disk_jsonl"])
        self.assertTrue(payload["web"])

    def test_ingest_server_serves_web_ui(self) -> None:
        server = create_server("127.0.0.1", 0, aggregator=LogAggregator())
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address
            with request.urlopen(f"http://{host}:{port}/", timeout=5) as response:
                html = response.read().decode("utf-8")
        finally:
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()

        self.assertIn("<title>ai_logger</title>", html)
        self.assertIn("Ask AI about these logs", html)

    def test_web_api_lists_projects_files_and_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "logs"
            project_dir = root / "alpha"
            project_dir.mkdir(parents=True)
            log_path = project_dir / "2026-07-07.jsonl"
            log_path.write_text(
                "\n".join(
                    [
                        json.dumps({"logger": "alpha.worker", "level": "INFO", "message": "ok"}),
                        json.dumps({"logger": "alpha.worker", "level": "ERROR", "message": "failed"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            server = create_server(
                "127.0.0.1",
                0,
                aggregator=LogAggregator(),
                web_logs=WebLogRepository(root),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                base_url = f"http://{host}:{port}"
                with request.urlopen(f"{base_url}/api/overview", timeout=5) as response:
                    overview = json.loads(response.read().decode("utf-8"))
                with request.urlopen(
                    f"{base_url}/api/logs?project=alpha&levels=ERROR",
                    timeout=5,
                ) as response:
                    logs = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                thread.join(timeout=3)
                server.server_close()

        self.assertEqual(overview["projects"][0]["name"], "alpha")
        self.assertEqual(overview["files"][0]["name"], "2026-07-07.jsonl")
        self.assertEqual(len(logs["records"]), 1)
        self.assertEqual(logs["records"][0]["message"], "failed")

    def test_web_search_uses_local_fallback_without_llm_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "logs"
            project_dir = root / "alpha"
            project_dir.mkdir(parents=True)
            (project_dir / "2026-07-07.jsonl").write_text(
                json.dumps(
                    {
                        "logger": "alpha.worker",
                        "level": "ERROR",
                        "message": "payment.failed",
                        "context": {"order_id": "42"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            server = create_server(
                "127.0.0.1",
                0,
                aggregator=LogAggregator(),
                web_logs=WebLogRepository(root),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                body = json.dumps({"query": "payment failed", "project": "alpha"}).encode("utf-8")
                http_request = request.Request(
                    f"http://{host}:{port}/api/search",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with patch.dict("os.environ", {}, clear=True):
                    with request.urlopen(http_request, timeout=5) as response:
                        result = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                thread.join(timeout=3)
                server.server_close()

        self.assertEqual(result["provider"], "local")
        self.assertIn("payment", result["summary"])
        self.assertEqual(result["matches"][0]["record"]["message"], "payment.failed")

    def test_web_search_can_use_configured_mock_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "logs"
            project_dir = root / "alpha"
            project_dir.mkdir(parents=True)
            (project_dir / "2026-07-07.jsonl").write_text(
                json.dumps(
                    {
                        "logger": "alpha.worker",
                        "level": "ERROR",
                        "message": "payment.failed",
                        "context": {"order_id": "42"},
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            server = create_server(
                "127.0.0.1",
                0,
                aggregator=LogAggregator(),
                web_logs=WebLogRepository(root),
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                host, port = server.server_address
                body = json.dumps(
                    {"query": "payment failed", "project": "alpha", "provider": "mock"}
                ).encode("utf-8")
                http_request = request.Request(
                    f"http://{host}:{port}/api/search",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with patch.dict(
                    "os.environ",
                    {
                        "AI_LOGGER_LLM_MOCK_RESPONSE": json.dumps(
                            {"summary": "Mock web analysis.", "matches": []}
                        ),
                    },
                    clear=False,
                ):
                    with request.urlopen(http_request, timeout=5) as response:
                        result = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                thread.join(timeout=3)
                server.server_close()

        self.assertEqual(result["provider"], "mock")
        self.assertEqual(result["summary"], "Mock web analysis.")

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
