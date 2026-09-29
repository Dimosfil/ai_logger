from __future__ import annotations

import json
import sys
import threading
import unittest
from pathlib import Path
from urllib import error, request

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger.aggregator import LogAggregator
from ai_logger.server import _bind_address_from_env, _database_settings_from_env, create_server


class FakeStore:
    def __init__(self):
        self.records = []
        self.fail = False

    def ping(self):
        return not self.fail

    def authorize(self, key, scope):
        return {("client", "ingest"): "media", ("agent", "read"): "media"}.get((key, scope), False)

    def insert_records(self, records):
        if self.fail:
            raise RuntimeError("db unavailable")
        self.records.extend(records)
        return records

    def read_records(self, *, project, levels, since, limit):
        return [record.to_dict() for record in self.records if record.context["project"] == project][:limit]

    def list_keys(self):
        return [{"id": 1, "name": "client", "key_prefix": "ail_public", "scopes": ["ingest"],
                 "project": "media", "created_at": "today", "revoked_at": None}]

    def create_key(self, name, scopes, project):
        return {"id": 2, "key": "issued-once", "name": name, "scopes": scopes, "project": project}

    def revoke_key(self, key_id):
        return key_id == 1


class HostedServerTests(unittest.TestCase):
    def test_platform_port_controls_the_bind_address(self):
        self.assertEqual(_bind_address_from_env({}), ("127.0.0.1", 8765))
        self.assertEqual(
            _bind_address_from_env({"PORT": "3000", "AI_LOGGER_SERVER_PORT": "8765"}),
            ("0.0.0.0", 3000),
        )
        self.assertEqual(
            _bind_address_from_env({"AI_LOGGER_SERVER_HOST": "127.0.0.1", "PORT": "3000"}),
            ("127.0.0.1", 3000),
        )

    def test_hosted_image_requires_database_and_strong_admin_token(self):
        with self.assertRaisesRegex(RuntimeError, "DATABASE_URL"):
            _database_settings_from_env({"AI_LOGGER_REQUIRE_POSTGRES": "1"})
        with self.assertRaisesRegex(RuntimeError, "at least 32"):
            _database_settings_from_env({
                "AI_LOGGER_REQUIRE_POSTGRES": "1", "DATABASE_URL": "postgresql://example",
                "AI_LOGGER_ADMIN_TOKEN": "short",
            })
        self.assertEqual(
            _database_settings_from_env({
                "AI_LOGGER_REQUIRE_POSTGRES": "1", "DATABASE_URL": "postgresql://example",
                "AI_LOGGER_ADMIN_TOKEN": "x" * 32,
            }),
            ("postgresql://example", "x" * 32),
        )

    def setUp(self):
        self.store = FakeStore()
        self.server = create_server("127.0.0.1", 0, aggregator=LogAggregator(),
                                    store=self.store, admin_token="admin-secret")
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.url = f"http://{host}:{port}"

    def tearDown(self):
        self.server.shutdown()
        self.thread.join(timeout=3)
        self.server.server_close()

    def call(self, path, *, key=None, body=None, method="GET"):
        headers = {"Content-Type": "application/json"}
        if key:
            headers["Authorization"] = f"Bearer {key}"
        payload = json.dumps(body).encode("utf-8") if body is not None else None
        req = request.Request(self.url + path, data=payload, headers=headers, method=method)
        try:
            with request.urlopen(req, timeout=5) as response:
                return response.status, json.load(response)
        except error.HTTPError as exc:
            with exc:
                return exc.code, json.load(exc)

    def test_client_and_agent_are_isolated_by_scope_and_project(self):
        record = {"logger": "media.worker", "level": "ERROR", "message": "failed",
                  "context": {"project": "media"}}
        self.assertEqual(self.call("/ingest", body=record, method="POST")[0], 401)
        self.assertEqual(self.call("/ingest", key="agent", body=record, method="POST")[0], 401)
        self.assertEqual(self.call("/ingest", key="client", body={**record, "context": {"project": "other"}}, method="POST")[0], 403)
        self.assertEqual(self.call("/ingest", key="client", body=record, method="POST")[0], 202)
        self.assertEqual(self.call("/api/agent/logs", key="client")[0], 401)
        self.assertEqual(self.call("/api/agent/logs?project=other", key="agent")[0], 403)
        status, result = self.call("/api/agent/logs", key="agent")
        self.assertEqual(status, 200)
        self.assertEqual(result["records"][0]["message"], "failed")
        self.assertEqual(self.call("/api/admin/keys", key="agent")[0], 401)

    def test_storage_failure_is_not_accepted(self):
        self.store.fail = True
        status, result = self.call("/ingest", key="client", method="POST", body={
            "logger": "media", "level": "ERROR", "message": "failed", "context": {"project": "media"},
        })
        self.assertEqual(status, 503)
        self.assertEqual(result["error"], "storage_unavailable")

    def test_admin_can_issue_and_revoke_key(self):
        status, result = self.call("/api/admin/keys", key="admin-secret", method="POST",
                                   body={"name": "new", "scopes": ["ingest", "read"], "project": "media"})
        self.assertEqual(status, 201)
        self.assertEqual(result["key"], "issued-once")
        self.assertEqual(self.call("/api/admin/keys/1", key="admin-secret", method="DELETE")[0], 200)


if __name__ == "__main__":
    unittest.main()
