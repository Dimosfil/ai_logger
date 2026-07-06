from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger import (
    DiskJsonLinesPlugin,
    GraylogGelfPlugin,
    LogAggregator,
    LogLevel,
    Logger,
    MemoryLogPlugin,
    ServerHttpPlugin,
    catch_and_log,
    configured_logger,
    get_tool_logger,
    log_exceptions,
)


class LoggingCoreTests(unittest.TestCase):
    def test_logger_emits_structured_records_to_memory_plugin(self) -> None:
        plugin = MemoryLogPlugin()
        aggregator = LogAggregator([plugin], default_context={"service": "tests"})
        logger = Logger("unit", aggregator).bind(request_id="abc")

        logger.info("task.started", task_id=42)

        self.assertEqual(len(plugin.records), 1)
        record = plugin.records[0]
        self.assertEqual(record.logger_name, "unit")
        self.assertEqual(record.level, LogLevel.INFO)
        self.assertEqual(record.context["service"], "tests")
        self.assertEqual(record.context["request_id"], "abc")
        self.assertEqual(record.context["task_id"], 42)

    def test_min_level_filters_low_priority_records(self) -> None:
        plugin = MemoryLogPlugin()
        logger = Logger("unit", LogAggregator([plugin], min_level=LogLevel.WARNING))

        logger.info("ignored")
        logger.warning("kept")

        self.assertEqual([record.message for record in plugin.records], ["kept"])

    def test_disk_plugin_writes_json_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "logs" / "app.jsonl"
            plugin = DiskJsonLinesPlugin(path)
            logger = Logger("unit", LogAggregator([plugin]))

            logger.error("task.failed", task_id="x")

            lines = path.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(lines), 1)
            payload = json.loads(lines[0])
            self.assertEqual(payload["message"], "task.failed")
            self.assertEqual(payload["context"]["task_id"], "x")

    def test_exception_helpers_log_and_reraise_by_default(self) -> None:
        plugin = MemoryLogPlugin()
        logger = Logger("unit", LogAggregator([plugin]))

        with self.assertRaises(ValueError):
            with log_exceptions(logger, "context.failed"):
                raise ValueError("bad")

        self.assertEqual(plugin.records[0].exception_type, "ValueError")
        self.assertIn("bad", plugin.records[0].exception_message or "")

    def test_decorator_can_swallow_and_return_default(self) -> None:
        plugin = MemoryLogPlugin()
        logger = Logger("unit", LogAggregator([plugin]))

        @catch_and_log(logger, "function.failed", reraise=False, default="fallback")
        def run() -> str:
            raise RuntimeError("broken")

        self.assertEqual(run(), "fallback")
        self.assertEqual(plugin.records[0].message, "function.failed")

    def test_plugin_failure_is_buffered_not_raised(self) -> None:
        class BrokenPlugin:
            name = "broken"

            def emit(self, _record):
                raise RuntimeError("sink down")

            def flush(self):
                return None

            def close(self):
                return None

        logger = Logger("unit", LogAggregator([BrokenPlugin()], error_stream=StringIO()))

        logger.info("delivery.test")

        self.assertEqual(len(logger.aggregator.failed_records), 1)
        _record, plugin_name, message = logger.aggregator.failed_records[0]
        self.assertEqual(plugin_name, "broken")
        self.assertIn("sink down", message)

    def test_configured_logger_uses_environment_plugins(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "app.jsonl")
            logger = configured_logger(
                "unit",
                environ={
                    "AI_LOGGER_LEVEL": "DEBUG",
                    "AI_LOGGER_SERVICE": "svc",
                    "AI_LOGGER_JSONL_PATH": path,
                },
            )

            logger.debug("configured")

            payload = json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["context"]["service"], "svc")
            self.assertEqual(payload["message"], "configured")

    def test_configured_logger_can_send_to_server(self) -> None:
        logger = configured_logger(
            "unit",
            environ={
                "AI_LOGGER_SERVER_URL": "http://localhost:8765/ingest",
                "AI_LOGGER_SERVER_TOKEN": "token",
            },
        )

        plugin = logger.aggregator._plugins[0]
        self.assertIsInstance(plugin, ServerHttpPlugin)
        self.assertEqual(plugin.headers["Authorization"], "Bearer token")

    def test_server_aggregator_can_configure_graylog_sink(self) -> None:
        from ai_logger import build_server_aggregator_from_env

        aggregator = build_server_aggregator_from_env(
            {"AI_LOGGER_GRAYLOG_GELF_URL": "http://localhost:12201/gelf"}
        )

        self.assertTrue(any(isinstance(plugin, GraylogGelfPlugin) for plugin in aggregator._plugins))

    def test_tool_logger_adds_tool_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "tool.jsonl")
            logger = get_tool_logger(
                "indexer",
                environ={"AI_LOGGER_JSONL_PATH": path},
                mode="rebuild",
            )

            logger.info("tool.started")

            payload = json.loads(Path(path).read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(payload["context"]["tool"], "indexer")
            self.assertEqual(payload["context"]["mode"], "rebuild")


if __name__ == "__main__":
    unittest.main()
