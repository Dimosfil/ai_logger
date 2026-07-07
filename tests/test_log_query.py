from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger.log_query import (  # noqa: E402
    ask_deepseek,
    format_records_for_prompt,
    load_jsonl_records,
    main,
)


class _FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class LogQueryTests(unittest.TestCase):
    def test_load_jsonl_records_filters_and_limits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"message": "one", "level": "INFO"}),
                        "not-json",
                        json.dumps({"message": "two failed", "level": "ERROR"}),
                        json.dumps({"message": "three failed", "level": "WARNING"}),
                    ]
                ),
                encoding="utf-8",
            )

            records = load_jsonl_records(path, limit=1, text_filter="failed")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["message"], "three failed")

    def test_load_jsonl_records_reads_project_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "projects"
            (root / "alpha").mkdir(parents=True)
            (root / "beta").mkdir(parents=True)
            (root / "alpha" / "2026-07-07.jsonl").write_text(
                json.dumps({"message": "alpha ok"}) + "\n",
                encoding="utf-8",
            )
            (root / "beta" / "2026-07-07.jsonl").write_text(
                json.dumps({"message": "beta failed"}) + "\n",
                encoding="utf-8",
            )

            records = load_jsonl_records(root, text_filter="failed")

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["message"], "beta failed")

    def test_format_records_for_prompt_keeps_compact_fields(self) -> None:
        context = format_records_for_prompt(
            [
                {
                    "timestamp": "2026-07-07T10:00:00+00:00",
                    "level": "ERROR",
                    "logger": "worker",
                    "message": "job.failed",
                    "context": {"job_id": "42"},
                }
            ]
        )

        self.assertIn('"message": "job.failed"', context)
        self.assertIn('"job_id": "42"', context)

    def test_ask_deepseek_sends_openai_compatible_request(self) -> None:
        requests = []

        def fake_urlopen(request, timeout):
            requests.append((request, timeout))
            return _FakeResponse({"choices": [{"message": {"content": "The job failed."}}]})

        with patch("ai_logger.log_query.request.urlopen", fake_urlopen):
            answer = ask_deepseek(
                question="What happened?",
                log_context='{"message":"job.failed"}',
                api_key="secret",
                timeout_seconds=3,
            )

        self.assertEqual(answer, "The job failed.")
        http_request, timeout = requests[0]
        payload = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(timeout, 3)
        self.assertEqual(http_request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(http_request.headers["Authorization"], "Bearer secret")
        self.assertEqual(payload["model"], "deepseek-v4-flash")

    def test_main_requires_deepseek_key_for_llm_call(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jsonl"
            path.write_text(json.dumps({"message": "job.failed"}) + "\n", encoding="utf-8")
            output = StringIO()
            with patch.dict("os.environ", {}, clear=True), patch("sys.stdout", output):
                code = main(["What happened?", "--logs-path", str(path)])

        self.assertEqual(code, 2)
        self.assertIn("DEEPSEEK_API_KEY", output.getvalue())

    def test_main_can_print_context_without_llm_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jsonl"
            path.write_text(json.dumps({"message": "job.failed"}) + "\n", encoding="utf-8")
            output = StringIO()
            with patch.dict("os.environ", {}, clear=True), patch("sys.stdout", output):
                code = main(["What happened?", "--logs-path", str(path), "--print-context"])

        self.assertEqual(code, 0)
        self.assertIn("job.failed", output.getvalue())


if __name__ == "__main__":
    unittest.main()
