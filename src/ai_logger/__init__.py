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
from .llm import DeepSeekChatClient, DeepSeekOptions, LlmProviderError
from .log_search import (
    DeepSeekLogSearchProvider,
    JsonlLogSource,
    LogSearchCandidate,
    LogSearchMatch,
    LogSearchResult,
    SmartLogSearcher,
)
from .logging_adapter import AiLoggerHttpHandler, log_record_from_python
from .logger import Logger
from .plugins import (
    ClickHouseHttpPlugin,
    DiskJsonLinesPlugin,
    GraylogGelfPlugin,
    HttpJsonPlugin,
    LogPlugin,
    MemoryLogPlugin,
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
    "DeepSeekChatClient",
    "DeepSeekLogSearchProvider",
    "DeepSeekOptions",
    "DiskJsonLinesPlugin",
    "GraylogGelfPlugin",
    "HttpJsonPlugin",
    "JsonlLogSource",
    "LlmProviderError",
    "LogIngestHttpServer",
    "LogAggregator",
    "LogLevel",
    "LogPlugin",
    "LogRecord",
    "LogSearchCandidate",
    "LogSearchMatch",
    "LogSearchResult",
    "Logger",
    "MemoryLogPlugin",
    "ServerHttpPlugin",
    "SmartLogSearcher",
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
