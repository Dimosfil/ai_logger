from __future__ import annotations

import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger.server_check import main  # noqa: E402


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class ServerCheckTests(unittest.TestCase):
    def test_server_check_reports_healthy_server(self) -> None:
        output = StringIO()

        def fake_urlopen(request, timeout):
            self.assertEqual(request.full_url, "http://logger.example/health")
            self.assertEqual(timeout, 2.0)
            return _FakeResponse({"status": "ok", "plugins": 1})

        with patch("ai_logger.server_check.request.urlopen", fake_urlopen), patch(
            "sys.stdout",
            output,
        ):
            code = main(["--url", "http://logger.example/health", "--timeout", "2"])

        self.assertEqual(code, 0)
        self.assertIn("healthy", output.getvalue())

    def test_server_check_returns_failure_for_unhealthy_payload(self) -> None:
        output = StringIO()
        with patch(
            "ai_logger.server_check.request.urlopen",
            return_value=_FakeResponse({"status": "down"}),
        ), patch("sys.stdout", output):
            code = main(["--url", "http://logger.example/health"])

        self.assertEqual(code, 1)
        self.assertIn("failed", output.getvalue())

    def test_server_check_uses_loopback_for_bind_all_host(self) -> None:
        output = StringIO()

        def fake_urlopen(request, timeout):
            self.assertEqual(request.full_url, "http://127.0.0.1:8765/health")
            return _FakeResponse({"status": "ok", "plugins": 1})

        with patch("ai_logger.server_check.request.urlopen", fake_urlopen), patch(
            "sys.stdout",
            output,
        ):
            code = main(["--host", "0.0.0.0", "--port", "8765"])

        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
