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
from .llm import (
    CodexAppServerChatClient,
    CodexAppServerOptions,
    DeepSeekChatClient,
    DeepSeekOptions,
    LlmProviderError,
    MockChatClient,
    OpenAiCompatibleChatClient,
    OpenAiCompatibleOptions,
)
from .log_search import (
    DeepSeekLogSearchProvider,
    JsonlLogSource,
    LogSearchCandidate,
    LogSearchMatch,
    LogSearchResult,
    SmartLogSearcher,
    StructuredLlmLogSearchProvider,
)
from .log_search_providers import create_log_search_llm_provider, normalize_log_search_provider
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
    "CodexAppServerChatClient",
    "CodexAppServerOptions",
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
    "MockChatClient",
    "OpenAiCompatibleChatClient",
    "OpenAiCompatibleOptions",
    "ProjectDailyJsonLinesPlugin",
    "ServerHttpPlugin",
    "SmartLogSearcher",
    "StructuredLlmLogSearchProvider",
    "build_aggregator_from_env",
    "build_client_from_env",
    "build_server_aggregator_from_env",
    "catch_and_log",
    "configured_logging_handler",
    "configured_logger",
    "create_server",
    "create_log_search_llm_provider",
    "get_tool_logger",
    "json_safe",
    "log_exceptions",
    "log_record_from_python",
    "normalize_log_search_provider",
    "redact_value",
]
