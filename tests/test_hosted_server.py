from __future__ import annotations

import json
import sys
import threading
import unittest
from http.client import RemoteDisconnected
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib import error, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger.aggregator import LogAggregator
from ai_logger.postgres_store import PostgresStore
from ai_logger.server import LogIngestHandler, _bind_address_from_env, _database_settings_from_env, create_server


class FakeStore:
    def __init__(self):
        self.records = []
        self.fail = False

    def ping(self):
        return not self.fail

    def insert_records(self, records):
        if self.fail:
            raise RuntimeError("db unavailable")
        self.records.extend(records)
        return records

    def read_records(self, *, project, levels, since, limit):
        return [
            record.to_dict() for record in self.records
            if (not project or record.context["project"] == project)
            and (not levels or record.level.name in levels)
        ][:limit]


class HostedServerTests(unittest.TestCase):
    def test_database_tls_is_opt_in(self):
        connect = Mock()
        with patch.dict(sys.modules, {"psycopg": SimpleNamespace(connect=connect)}):
            PostgresStore("postgresql://example/db")._connect()
            self.assertEqual(connect.call_args.kwargs["sslmode"], "disable")
            PostgresStore("postgresql://example/db", ssl=True)._connect()
            self.assertEqual(connect.call_args.kwargs["sslmode"], "require")

    def test_platform_port_controls_the_bind_address(self):
        self.assertEqual(_bind_address_from_env({}), ("127.0.0.1", 8766))
        self.assertEqual(
            _bind_address_from_env({"PORT": "3000", "AI_LOGGER_SERVER_PORT": "8766"}),
            ("0.0.0.0", 3000),
        )

    def test_hosted_image_requires_only_database(self):
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
            _database_settings_from_env({"AI_LOGGER_REQUIRE_POSTGRES": "1"})
        self.assertEqual(
            _database_settings_from_env({
                "AI_LOGGER_REQUIRE_POSTGRES": "1",
                "DATABASE_URL": "postgresql://example",
            }),
            "postgresql://example",
        )

    def setUp(self):
        self.store = FakeStore()
        self.server = create_server("127.0.0.1", 0, aggregator=LogAggregator(), store=self.store)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()

    def call(self, path, *, body=None, method="GET"):
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        req = request.Request(self.url + path, data=payload,
                              headers={"Content-Type": "application/json"}, method=method)
        try:
            with request.urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except error.HTTPError as exc:
            with exc:
                return exc.code, json.load(exc)

    def test_ingest_and_read_work_without_keys(self):
        record = {"logger": "media.worker", "level": "ERROR", "message": "failed",
                  "context": {"project": "media"}}
        self.assertEqual(self.call("/ingest", body=record, method="POST")[0], 202)
        status, result = self.call("/api/agent/logs?project=media")
        self.assertEqual(status, 200)
        self.assertEqual(result["records"][0]["message"], "failed")
        self.assertEqual(self.call("/api/overview")[0], 200)
        self.assertEqual(self.call("/api/admin/keys")[0], 404)

    def test_admin_opens_without_password(self):
        for path in ("/", "/admin"):
            with request.urlopen(self.url + path, timeout=5) as response:
                html = response.read().decode("utf-8")
                self.assertEqual(response.status, 200)
                self.assertIn("/api/agent/logs", html)
                self.assertNotIn("adminToken", html)

    def test_read_filters_multiple_levels_with_project_and_limit(self):
        for project, level in (("media", "INFO"), ("media", "ERROR"),
                               ("other", "ERROR"), ("media", "WARNING")):
            self.assertEqual(self.call("/ingest", method="POST", body={
                "logger": "worker", "level": level, "message": level,
                "context": {"project": project},
            })[0], 202)
        status, result = self.call("/api/agent/logs?project=media&levels=ERROR,WARNING&limit=100")
        self.assertEqual(status, 200)
        self.assertEqual([record["level"] for record in result["records"]], ["ERROR", "WARNING"])
        self.assertTrue(all(record["context"]["project"] == "media" for record in result["records"]))
        self.assertEqual(len(self.call("/api/agent/logs?project=media&levels=ERROR,WARNING&limit=1")[1]["records"]), 1)
        self.assertEqual(len(self.call("/api/agent/logs?project=media")[1]["records"]), 3)

    def test_read_api_preserves_machine_identity_and_role(self):
        for machine in ("my-pc", "friend-pc"):
            self.assertEqual(self.call("/ingest", method="POST", body={
                "logger": "media", "level": "INFO", "message": "machine.check",
                "context": {"project": "media", "instance_id": machine,
                            "service": "executor", "environment": "local"},
            })[0], 202)
        status, result = self.call("/api/agent/logs?project=media")
        self.assertEqual(status, 200)
        self.assertEqual(
            {record["context"]["instance_id"] for record in result["records"]},
            {"my-pc", "friend-pc"},
        )
        self.assertTrue(all(record["context"]["service"] == "executor"
                            for record in result["records"]))

    def test_storage_failure_is_not_accepted(self):
        self.store.fail = True
        status, result = self.call("/ingest", method="POST", body={
            "logger": "media", "level": "ERROR", "message": "failed",
            "context": {"project": "media"},
        })
        self.assertEqual(status, 503)
        self.assertEqual(result["error"], "storage_unavailable")

    def test_ingest_stays_stored_when_response_connection_breaks(self):
        with patch.object(LogIngestHandler, "end_headers", side_effect=BrokenPipeError), \
                patch.object(self.server, "handle_error") as handle_error:
            with self.assertRaises(RemoteDisconnected):
                self.call("/ingest", method="POST", body={
                    "logger": "worker", "level": "ERROR", "message": "saved",
                    "context": {"project": "media"},
                })
            handle_error.assert_not_called()
        self.assertEqual(self.call("/health")[0], 200)
        status, result = self.call("/api/agent/logs?project=media")
        self.assertEqual(status, 200)
        self.assertEqual([record["message"] for record in result["records"]], ["saved"])

    def test_error_details_survive_ingest_and_read(self):
        exception = {"type": "ConfigError", "message": "Missing port setting",
                     "stack_trace": "ConfigError: Missing port setting\n at load (config.js:12:3)"}
        context = {"project": "media", "description": "Missing port setting",
                   "file": "src/config.js", "line": 12, "entity": "executor"}
        status, _ = self.call("/ingest", method="POST", body={
            "logger": "media.startup", "level": "ERROR", "message": "startup.error",
            "context": context, "exception": exception,
        })
        self.assertEqual(status, 202)
        status, result = self.call("/api/agent/logs?project=media")
        self.assertEqual(status, 200)
        self.assertEqual(result["records"][0]["exception"], exception)
        self.assertEqual(result["records"][0]["context"], context)


if __name__ == "__main__":
    unittest.main()
