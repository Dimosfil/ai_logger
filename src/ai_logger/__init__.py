"""Universal plugin-based logging core."""

from .aggregator import LogAggregator
from .client import AiLoggerClient, AiLoggerClientOptions, json_safe, redact_value
from .config import (
    build_aggregator_from_env,
    build_client_from_env,
    build_server_aggregator_from_env,
    configured_logging_handler,
    configured_logger,
)
from .context import catch_and_log, log_exceptions
from .levels import LogLevel
from .logging_adapter import AiLoggerHttpHandler, log_record_from_python
from .logger import Logger
from .plugins import (
    ClickHouseHttpPlugin,
    DiskJsonLinesPlugin,
    GraylogGelfPlugin,
    HttpJsonPlugin,
    LogPlugin,
    MemoryLogPlugin,
    ProjectDailyJsonLinesPlugin,
    ServerHttpPlugin,
)
from .records import LogRecord
from .server import LogIngestHttpServer, create_server
from .tool_logging import get_tool_logger

__all__ = [
    "AiLoggerClient",
    "AiLoggerClientOptions",
    "AiLoggerHttpHandler",
    "ClickHouseHttpPlugin",
    "DiskJsonLinesPlugin",
    "GraylogGelfPlugin",
    "HttpJsonPlugin",
    "LogIngestHttpServer",
    "LogAggregator",
    "LogLevel",
    "LogPlugin",
    "LogRecord",
    "Logger",
    "MemoryLogPlugin",
    "ProjectDailyJsonLinesPlugin",
    "ServerHttpPlugin",
    "build_aggregator_from_env",
    "build_client_from_env",
    "build_server_aggregator_from_env",
    "catch_and_log",
    "configured_logging_handler",
    "configured_logger",
    "create_server",
    "get_tool_logger",
    "json_safe",
    "log_exceptions",
    "log_record_from_python",
    "redact_value",
]
