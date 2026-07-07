from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger import (  # noqa: E402
    DeepSeekChatClient,
    DeepSeekLogSearchProvider,
    DeepSeekOptions,
    DiskJsonLinesPlugin,
    JsonlLogSource,
    LogAggregator,
    LogLevel,
    Logger,
    OpenAiCompatibleChatClient,
    OpenAiCompatibleOptions,
    SmartLogSearcher,
)
from ai_logger.log_search_providers import create_log_search_llm_provider  # noqa: E402
from ai_logger.log_search import LlmLogSearchAnalysis  # noqa: E402
from ai_logger.log_search_cli import main as log_search_main  # noqa: E402


class _FakeSearchProvider:
    name = "fake"

    def analyze(self, query, candidates, *, top_k):
        self.query = query
        self.candidates = candidates
        self.top_k = top_k
        return LlmLogSearchAnalysis(
            summary="Authorization failures are clustered in the API service.",
            matches=[
                (
                    candidates[0].record.record_id,
                    "This record contains the auth failure and request id.",
                )
            ],
        )


class _FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


class LogSearchTests(unittest.TestCase):
    def test_local_search_returns_relevant_jsonl_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jsonl"
            logger = Logger("api.auth", LogAggregator([DiskJsonLinesPlugin(path)]))
            logger.info("request.completed", route="/health")
            logger.error("authorization.failed", user_id="42", request_id="req-1")

            result = SmartLogSearcher(JsonlLogSource(path)).search(
                "authorization problem req-1",
                top_k=1,
            )

            self.assertEqual(result.provider, "local")
            self.assertEqual(len(result.matches), 1)
            self.assertEqual(result.matches[0].record.message, "authorization.failed")

    def test_llm_provider_can_rerank_and_explain_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jsonl"
            logger = Logger("api.auth", LogAggregator([DiskJsonLinesPlugin(path)]))
            logger.error("authorization.failed", request_id="req-1")
            provider = _FakeSearchProvider()

            result = SmartLogSearcher(
                JsonlLogSource(path),
                llm_provider=provider,
            ).search("auth fails", top_k=1)

            self.assertEqual(result.provider, "fake")
            self.assertEqual(result.summary, "Authorization failures are clustered in the API service.")
            self.assertEqual(result.matches[0].reason, "This record contains the auth failure and request id.")
            self.assertEqual(provider.top_k, 1)

    def test_deepseek_client_posts_chat_completion_json_request(self) -> None:
        requests = []
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "Found the failing auth request.",
                                "matches": [{"id": "abc", "reason": "auth error"}],
                            }
                        )
                    }
                }
            ]
        }

        def fake_urlopen(http_request, timeout):
            requests.append((http_request, timeout))
            return _FakeResponse(response_payload)

        client = DeepSeekChatClient(
            DeepSeekOptions(
                api_key="test-key",
                base_url="https://api.deepseek.com",
                model="deepseek-v4-flash",
                timeout_seconds=7,
                max_tokens=300,
            )
        )
        with patch("ai_logger.llm.request.urlopen", fake_urlopen):
            result = client.complete_json("system", "user")

        http_request, timeout = requests[0]
        payload = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(timeout, 7)
        self.assertEqual(http_request.full_url, "https://api.deepseek.com/chat/completions")
        self.assertEqual(http_request.headers["Authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "deepseek-v4-flash")
        self.assertEqual(payload["response_format"], {"type": "json_object"})
        self.assertEqual(result["matches"][0]["id"], "abc")

    def test_openai_compatible_client_posts_chat_completion_json_request(self) -> None:
        requests = []
        response_payload = {
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "summary": "Found a worker timeout.",
                                "matches": [{"id": "worker-1", "reason": "timeout"}],
                            }
                        )
                    }
                }
            ]
        }

        def fake_urlopen(http_request, timeout):
            requests.append((http_request, timeout))
            return _FakeResponse(response_payload)

        client = OpenAiCompatibleChatClient(
            OpenAiCompatibleOptions(
                api_key="test-key",
                base_url="https://llm.example.test/v1/",
                model="custom-model",
                timeout_seconds=5,
                max_tokens=111,
            )
        )
        with patch("ai_logger.llm.request.urlopen", fake_urlopen):
            result = client.complete_json("system", "user")

        http_request, timeout = requests[0]
        payload = json.loads(http_request.data.decode("utf-8"))
        self.assertEqual(timeout, 5)
        self.assertEqual(http_request.full_url, "https://llm.example.test/v1/chat/completions")
        self.assertEqual(http_request.headers["Authorization"], "Bearer test-key")
        self.assertEqual(payload["model"], "custom-model")
        self.assertEqual(payload["max_tokens"], 111)
        self.assertEqual(result["matches"][0]["id"], "worker-1")

    def test_deepseek_log_search_provider_formats_candidates(self) -> None:
        class FakeClient:
            def complete_json(self, system_prompt, user_prompt):
                self.system_prompt = system_prompt
                self.user_prompt = user_prompt
                payload = json.loads(user_prompt)
                return {
                    "summary": "The first candidate matches.",
                    "matches": [{"id": payload["candidate_logs"][0]["id"], "reason": "best"}],
                }

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jsonl"
            Logger("api", LogAggregator([DiskJsonLinesPlugin(path)])).error(
                "token rejected",
                token="secret",
            )
            provider = DeepSeekLogSearchProvider(FakeClient())
            result = SmartLogSearcher(JsonlLogSource(path), llm_provider=provider).search(
                "token rejected",
                top_k=1,
            )

        self.assertEqual(result.provider, "deepseek")
        self.assertEqual(result.matches[0].reason, "best")
        self.assertIn("[REDACTED]", provider.client.user_prompt)
        self.assertNotIn("secret", provider.client.user_prompt)

    def test_cli_can_run_local_json_output_without_api_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jsonl"
            Logger("worker", LogAggregator([DiskJsonLinesPlugin(path)])).error("job.failed")

            with patch("builtins.print") as fake_print:
                exit_code = log_search_main(
                    [
                        "job failed",
                        "--jsonl-path",
                        str(path),
                        "--no-llm",
                        "--format",
                        "json",
                    ]
                )

        self.assertEqual(exit_code, 0)
        output = fake_print.call_args.args[0]
        self.assertEqual(json.loads(output)["provider"], "local")

    def test_provider_registry_can_create_mock_log_search_provider(self) -> None:
        provider = create_log_search_llm_provider(
            "mock",
            environ={
                "AI_LOGGER_LLM_MOCK_RESPONSE": json.dumps(
                    {"summary": "Mock selected candidate.", "matches": []}
                )
            },
        )

        self.assertIsNotNone(provider)
        self.assertEqual(provider.name, "mock")

    def test_cli_can_use_mock_provider_for_search_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "server.jsonl"
            logger = Logger("worker", LogAggregator([DiskJsonLinesPlugin(path)]))
            logger.error("job.failed", job_id="42")

            with patch.dict(
                "os.environ",
                {
                    "AI_LOGGER_LLM_MOCK_RESPONSE": json.dumps(
                        {"summary": "Mock analysis.", "matches": []}
                    )
                },
                clear=False,
            ):
                with patch("builtins.print") as fake_print:
                    exit_code = log_search_main(
                        [
                            "job failed",
                            "--jsonl-path",
                            str(path),
                            "--provider",
                            "mock",
                            "--format",
                            "json",
                        ]
                    )

        self.assertEqual(exit_code, 0)
        output = fake_print.call_args.args[0]
        self.assertEqual(json.loads(output)["provider"], "mock")


if __name__ == "__main__":
    unittest.main()
