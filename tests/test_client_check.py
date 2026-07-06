from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger.client_check import main  # noqa: E402


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return b'{"accepted":1}'


class ClientCheckTests(unittest.TestCase):
    def test_client_check_requires_server_url(self) -> None:
        output = StringIO()
        with patch("sys.stdout", output):
            code = main([])

        self.assertEqual(code, 2)
        self.assertIn("AI_LOGGER_SERVER_URL", output.getvalue())

    def test_client_check_sends_test_event(self) -> None:
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse()

        output = StringIO()
        with patch("ai_logger.client.request.urlopen", fake_urlopen), patch("sys.stdout", output):
            code = main(
                [
                    "--server-url",
                    "http://logger.example/ingest",
                    "--token",
                    "secret",
                    "--project",
                    "target",
                    "--service",
                    "worker",
                    "--environment",
                    "test",
                    "--host",
                    "test-host",
                    "--message",
                    "install.check",
                ]
            )

        self.assertEqual(code, 0)
        http_request, timeout = requests[0]
        payload = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(timeout, 5.0)
        self.assertEqual(http_request.headers["Authorization"], "Bearer secret")
        self.assertEqual(payload["message"], "install.check")
        self.assertEqual(payload["context"]["project"], "target")
        self.assertEqual(payload["context"]["service"], "worker")
        self.assertEqual(payload["context"]["environment"], "test")
        self.assertEqual(payload["context"]["host"], "test-host")
        self.assertIn("delivered", output.getvalue())

    def test_client_check_writes_fallback_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fallback = Path(tmp) / "fallback.jsonl"
            output = StringIO()
            with (
                patch("ai_logger.client.request.urlopen", side_effect=OSError("down")),
                patch("sys.stdout", output),
            ):
                code = main(
                    [
                        "--server-url",
                        "http://logger.example/ingest",
                        "--fallback-jsonl-path",
                        str(fallback),
                    ]
                )

            self.assertEqual(code, 1)
            self.assertIn("failed", output.getvalue())
            payload = json.loads(fallback.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["message"], "ai_logger.client_check")


if __name__ == "__main__":
    unittest.main()
