from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from .aggregator import LogAggregator
from .client import AiLoggerClient, AiLoggerClientOptions
from .logging_adapter import AiLoggerHttpHandler
from .logger import Logger
from .plugins import (
    ClickHouseHttpPlugin,
    DiskJsonLinesPlugin,
    GraylogGelfPlugin,
    HttpJsonPlugin,
    ProjectDailyJsonLinesPlugin,
    ServerHttpPlugin,
)


def build_aggregator_from_env(
    environ: Mapping[str, str] | None = None,
    *,
    default_context: dict[str, Any] | None = None,
) -> LogAggregator:
    env = environ or os.environ
    context = dict(default_context or {})
    service = env.get("AI_LOGGER_SERVICE")
    if service:
        context.setdefault("service", service)

    aggregator = LogAggregator(
        min_level=env.get("AI_LOGGER_LEVEL", "INFO"),
        default_context=context,
    )

    jsonl_path = env.get("AI_LOGGER_JSONL_PATH")
    if jsonl_path:
        aggregator.add_plugin(DiskJsonLinesPlugin(jsonl_path))

    http_url = env.get("AI_LOGGER_HTTP_URL")
    if http_url:
        aggregator.add_plugin(
            HttpJsonPlugin(
                http_url,
                timeout_seconds=float(env.get("AI_LOGGER_HTTP_TIMEOUT", "5")),
            )
        )

    server_url = env.get("AI_LOGGER_SERVER_URL")
    if server_url:
        aggregator.add_plugin(
            ServerHttpPlugin(
                server_url,
                token=env.get("AI_LOGGER_SERVER_TOKEN"),
                timeout_seconds=float(env.get("AI_LOGGER_SERVER_TIMEOUT", "5")),
            )
        )

    return aggregator


def configured_logger(
    name: str,
    *,
    environ: Mapping[str, str] | None = None,
    context: dict[str, Any] | None = None,
) -> Logger:
    return Logger(
        name,
        build_aggregator_from_env(environ, default_context=context),
    )


def build_client_from_env(environ: Mapping[str, str] | None = None) -> AiLoggerClient:
    env = environ or os.environ
    server_url = env.get("AI_LOGGER_SERVER_URL")
    if not server_url:
        raise ValueError("AI_LOGGER_SERVER_URL is required to build an ai_logger client.")
    return AiLoggerClient(
        AiLoggerClientOptions(
            server_url=server_url,
            token=env.get("AI_LOGGER_SERVER_TOKEN"),
            project=env.get("AI_LOGGER_PROJECT"),
            service=env.get("AI_LOGGER_SERVICE"),
            environment=env.get("AI_LOGGER_ENVIRONMENT"),
            host=env.get("AI_LOGGER_HOST"),
            timeout_seconds=float(env.get("AI_LOGGER_HTTP_TIMEOUT", "5")),
            fallback_jsonl_path=env.get("AI_LOGGER_FALLBACK_JSONL_PATH"),
        )
    )


def configured_logging_handler(
    *,
    environ: Mapping[str, str] | None = None,
) -> AiLoggerHttpHandler:
    return AiLoggerHttpHandler(build_client_from_env(environ))


def build_server_aggregator_from_env(
    environ: Mapping[str, str] | None = None,
) -> LogAggregator:
    env = environ or os.environ
    aggregator = LogAggregator(
        min_level=env.get("AI_LOGGER_SERVER_LEVEL", env.get("AI_LOGGER_LEVEL", "DEBUG")),
        default_context={"node": env.get("AI_LOGGER_SERVER_NODE", "local")},
    )

    jsonl_path = env.get("AI_LOGGER_SERVER_JSONL_PATH")
    if jsonl_path:
        aggregator.add_plugin(DiskJsonLinesPlugin(jsonl_path))

    project_daily_dir = env.get("AI_LOGGER_SERVER_PROJECT_DAILY_DIR")
    if project_daily_dir:
        aggregator.add_plugin(ProjectDailyJsonLinesPlugin(project_daily_dir))

    graylog_url = env.get("AI_LOGGER_GRAYLOG_GELF_URL")
    if graylog_url:
        aggregator.add_plugin(
            GraylogGelfPlugin(
                graylog_url,
                host=env.get("AI_LOGGER_GRAYLOG_HOST"),
                timeout_seconds=float(env.get("AI_LOGGER_GRAYLOG_TIMEOUT", "5")),
            )
        )

    clickhouse_url = env.get("AI_LOGGER_CLICKHOUSE_URL")
    clickhouse_table = env.get("AI_LOGGER_CLICKHOUSE_TABLE")
    if clickhouse_url and clickhouse_table:
        aggregator.add_plugin(
            ClickHouseHttpPlugin(
                clickhouse_url,
                table=clickhouse_table,
                timeout_seconds=float(env.get("AI_LOGGER_CLICKHOUSE_TIMEOUT", "5")),
            )
        )

    return aggregator
