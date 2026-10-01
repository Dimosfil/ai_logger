from __future__ import annotations

import sys
import unittest
from http import HTTPStatus
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger.server import LogIngestHandler


class ResponseDisconnectTests(unittest.TestCase):
    def handler(self):
        handler = object.__new__(LogIngestHandler)
        handler.send_response = Mock()
        handler.send_header = Mock()
        handler.end_headers = Mock()
        handler.wfile = Mock()
        handler.close_connection = False
        return handler

    def test_disconnects_in_headers_and_body_close_json_and_html_connections(self):
        for error_type in (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            for stage in ("headers", "body"):
                for kind in ("json", "html"):
                    with self.subTest(error=error_type, stage=stage, kind=kind):
                        handler = self.handler()
                        writer = handler.end_headers if stage == "headers" else handler.wfile.write
                        writer.side_effect = error_type("client disconnected")
                        if kind == "json":
                            handler._send_json(HTTPStatus.OK, {"status": "ok"})
                        else:
                            handler._send_html(HTTPStatus.OK, "<p>ok</p>")
                        self.assertTrue(handler.close_connection)
                        if stage == "headers":
                            handler.wfile.write.assert_not_called()

    def test_other_io_errors_are_not_hidden(self):
        handler = self.handler()
        handler.wfile.write.side_effect = OSError("unexpected I/O failure")
        with self.assertRaisesRegex(OSError, "unexpected I/O failure"):
            handler._send_json(HTTPStatus.OK, {})
        self.assertFalse(handler.close_connection)


if __name__ == "__main__":
    unittest.main()
