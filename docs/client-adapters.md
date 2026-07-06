# Client Adapters

Projects may already use their native logging framework. ai_logger should not
replace that framework by default. Instead, each project installs or configures
an adapter that forwards native log events to the ai_logger ingest protocol.

## Adapter Model

```text
Project logging framework
  -> ai_logger client adapter
  -> AiLoggerClient core
  -> ai_logger server /ingest
  -> server backend plugins
```

Examples:

| Stack | Native logger | Adapter shape |
| --- | --- | --- |
| Python | `logging`, `structlog`, `loguru` | Handler/sink that converts native events to `LogRecord` and sends them with `AiLoggerClient` |
| .NET | `NLog` | NLog target |
| .NET | `log4net` | Appender |
| .NET | `Serilog` | Sink |
| .NET / ASP.NET Core | `Microsoft.Extensions.Logging` | `ILoggerProvider` |
| Node.js | `pino` | Transport |
| Node.js | `winston` | Transport |
| Java/Kotlin | Logback/Log4j2 | Appender |
| Go | `slog`, `zap`, `zerolog` | Handler/core/writer |

## Client Core

`AiLoggerClient` is the framework-neutral client. Adapters should depend on it
instead of implementing HTTP delivery themselves.

The client core owns:

- ingest URL and optional bearer token;
- default context such as project, service, environment, and host;
- JSON serialization for one record or a batch;
- redaction for common secret fields such as token, password, authorization,
  cookie, private key, and secret;
- optional fallback JSON Lines output when delivery fails;
- delivery failure tracking without raising into the application logging path.

Python projects can configure a native `logging.Handler`:

```python
import logging

from ai_logger import AiLoggerClientOptions, AiLoggerHttpHandler

handler = AiLoggerHttpHandler(
    options=AiLoggerClientOptions(
        server_url="http://127.0.0.1:8765/ingest",
        token="dev-secret",
        project="billing",
        service="worker",
        environment="dev",
        fallback_jsonl_path="logs/ai_logger_fallback.jsonl",
    )
)

logger = logging.getLogger("billing.worker")
logger.addHandler(handler)
logger.setLevel(logging.INFO)

logger.info("job.started", extra={"job_id": "42"})
```

The same handler can be built from environment variables:

```python
import logging

from ai_logger import configured_logging_handler

logging.getLogger("billing.worker").addHandler(configured_logging_handler())
```

Supported client environment variables:

- `AI_LOGGER_SERVER_URL`
- `AI_LOGGER_SERVER_TOKEN`
- `AI_LOGGER_PROJECT`
- `AI_LOGGER_SERVICE`
- `AI_LOGGER_ENVIRONMENT`
- `AI_LOGGER_HOST`
- `AI_LOGGER_HTTP_TIMEOUT`
- `AI_LOGGER_FALLBACK_JSONL_PATH`

## Agent Configuration Flow

The project agent configures the adapter inside the target project:

1. Detect the project's logging framework and runtime.
2. Add the matching ai_logger adapter package or local bridge.
3. Configure server URL, bearer token, project, service, and environment.
4. Preserve existing project logging behavior unless the user asks to replace
   it.
5. Add logs at meaningful boundaries in project code when they are missing.
6. Verify that a test event reaches the ai_logger server.

## Future ASP.NET Core Shape

ASP.NET Core should use the same model through a native logging provider:

```csharp
builder.Logging.AddAiLogger(options =>
{
    options.ServerUrl = "http://127.0.0.1:8765/ingest";
    options.Token = "dev-secret";
    options.Project = "billing";
    options.Service = "api";
    options.Environment = builder.Environment.EnvironmentName;
});
```

Application code should continue to use normal `ILogger<T>` APIs. The provider
will convert category, level, message template fields, exception details,
`Activity.TraceId`, `Activity.SpanId`, and request identifiers into the shared
ingest protocol.

## Server Responsibilities

The server owns backend selection. A project client should not need to know
whether logs are stored in Graylog, ClickHouse, JSONL, Loki, OpenTelemetry, or a
custom sink.

```text
Client adapter sends one normalized protocol.
Server plugins decide where records go.
```
