from __future__ import annotations

import json
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger.graylog_check import main  # noqa: E402


class _FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return b""


class GraylogCheckTests(unittest.TestCase):
    def test_graylog_check_requires_url(self) -> None:
        output = StringIO()
        with patch("sys.stdout", output):
            code = main([])

        self.assertEqual(code, 2)
        self.assertIn("AI_LOGGER_GRAYLOG_GELF_URL", output.getvalue())

    def test_graylog_check_sends_gelf_event(self) -> None:
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse()

        output = StringIO()
        with patch("ai_logger.plugins.request.urlopen", fake_urlopen), patch(
            "sys.stdout",
            output,
        ):
            code = main(
                [
                    "--url",
                    "http://graylog.example/gelf",
                    "--host",
                    "test-host",
                    "--timeout",
                    "2",
                    "--message",
                    "graylog.install.check",
                ]
            )

        self.assertEqual(code, 0)
        http_request, timeout = requests[0]
        payload = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(timeout, 2.0)
        self.assertEqual(payload["version"], "1.1")
        self.assertEqual(payload["host"], "test-host")
        self.assertEqual(payload["short_message"], "graylog.install.check")
        self.assertEqual(payload["_check"], "graylog_backend")
        self.assertEqual(payload["_tags"], "deploy,graylog")
        self.assertIn("delivered", output.getvalue())


if __name__ == "__main__":
    unittest.main()
