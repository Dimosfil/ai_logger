# ai_logger

`ai_logger` is a small universal logging platform with two deployable parts:

- **client adapters**: installed into any project and configured by that
  project's agent. Adapters may target Python logging, NLog, log4net, Serilog,
  pino, winston, Logback, Go slog, or another native logging framework;
- **local/server process**: receives logs and routes them to selected backends
  such as JSONL, Graylog GELF, ClickHouse, or future plugins.

The Python package in this repository is the first reference SDK and server
implementation. The cross-stack contract is the HTTP ingest protocol, not the
Python API.

Inside a client adapter, logging still has three layers:

- application code emits structured `LogRecord` data through `Logger`;
- `LogAggregator` enriches, filters, buffers, and fans records out;
- output plugins decide where records go, such as JSON Lines on disk or HTTP.

The package is intentionally dependency-free so it can be embedded into agents,
services, scripts, and tools before a larger observability stack exists.

See also:

- [Ingest protocol](docs/ingest-protocol.md)
- [Client adapters](docs/client-adapters.md)
- [Agent install guide](docs/agent-install.md)
- [Adapter manifest](docs/adapter-manifest.json)
- [Server deploy guide](docs/server-deploy.md)
- [Server deploy manifest](docs/server-deploy-manifest.json)
- [Windows no-Docker deploy entrypoint](deploy/windows/README.md)
- [Local Graylog deployment](deploy/graylog/README.md)

## Plugin Configuration

The helper `configured_logger()` can build plugins from environment variables:

- `AI_LOGGER_LEVEL`: minimum level, for example `INFO` or `DEBUG`;
- `AI_LOGGER_SERVICE`: static service name added to every record;
- `AI_LOGGER_JSONL_PATH`: enables `DiskJsonLinesPlugin`;
- `AI_LOGGER_HTTP_URL`: enables `HttpJsonPlugin`;
- `AI_LOGGER_SERVER_URL`: enables `ServerHttpPlugin`, usually
  `http://127.0.0.1:8765/ingest`;
- `AI_LOGGER_SERVER_TOKEN`: bearer token for the ingest server;
- `AI_LOGGER_HTTP_TIMEOUT`: HTTP timeout in seconds.

## Install

```powershell
python -m pip install -e .
```

## Quick Start

```python
from ai_logger import DiskJsonLinesPlugin, LogAggregator, Logger, catch_and_log

aggregator = LogAggregator()
aggregator.add_plugin(DiskJsonLinesPlugin("logs/app.jsonl"))

logger = Logger("worker", aggregator)
logger.info("worker.started", task_id="demo")

try:
    raise RuntimeError("boom")
except Exception as exc:
    logger.exception("worker.failed", exc, task_id="demo")

@catch_and_log(logger, "worker.crashed")
def run_job():
    raise ValueError("bad input")
```

For command-style components, `get_tool_logger("indexer")` creates a configured
logger and adds `{"tool": "indexer"}` to every record.

## Client / Server Mode

Python projects can use the reference SDK directly. Other stacks should use a
native adapter that sends the same ingest protocol.

```python
from ai_logger import Logger, LogAggregator, ServerHttpPlugin

aggregator = LogAggregator([
    ServerHttpPlugin("http://127.0.0.1:8765/ingest", token="dev-secret")
])
logger = Logger("my-project.worker", aggregator)

logger.info("job.started", job_id="42")
```

The same client route can be configured by environment:

```powershell
$env:AI_LOGGER_SERVER_URL = "http://127.0.0.1:8765/ingest"
$env:AI_LOGGER_SERVER_TOKEN = "dev-secret"
```

## Native Client Adapters

Framework adapters use `AiLoggerClient` as a common client core. The first
prototype adapter is a Python `logging.Handler`:

```python
import logging

from ai_logger import AiLoggerClientOptions, AiLoggerHttpHandler

handler = AiLoggerHttpHandler(
    options=AiLoggerClientOptions(
        server_url="http://127.0.0.1:8765/ingest",
        token="dev-secret",
        project="demo",
        service="worker",
        environment="dev",
    )
)

logging.getLogger("demo.worker").addHandler(handler)
```

Future adapters should keep the same shape: native framework event ->
normalized record -> `AiLoggerClient` -> `/ingest`.

After installing the package in another project, an agent can verify the client
configuration with:

```powershell
ai-logger-client-check
```

## Server

The server receives normalized records at `/ingest` and fans them out to the
configured backend plugins.

```powershell
$env:AI_LOGGER_SERVER_TOKEN = "dev-secret"
$env:AI_LOGGER_SERVER_JSONL_PATH = "logs/server.jsonl"
python -m ai_logger.server
```

After installation, the console command is also available:

```powershell
ai-logger-server
```

The server exposes a health endpoint:

```powershell
ai-logger-server-check
Invoke-RestMethod -Uri "http://127.0.0.1:8765/health"
```

Server backend environment variables:

- `AI_LOGGER_SERVER_HOST`: default `127.0.0.1`;
- `AI_LOGGER_SERVER_PORT`: default `8765`;
- `AI_LOGGER_SERVER_TOKEN`: optional bearer token required by `/ingest`;
- `AI_LOGGER_SERVER_JSONL_PATH`: write accepted logs to JSON Lines;
- `AI_LOGGER_SERVER_PROJECT_DAILY_DIR`: write accepted logs to
  `<dir>/<project>/YYYY-MM-DD.jsonl`;
- `AI_LOGGER_GRAYLOG_GELF_URL`: forward logs to a Graylog GELF HTTP input;
- `AI_LOGGER_GRAYLOG_HOST`: GELF `host` value;
- `AI_LOGGER_GRAYLOG_TIMEOUT`: Graylog request timeout in seconds;
- `AI_LOGGER_CLICKHOUSE_URL`: ClickHouse HTTP endpoint;
- `AI_LOGGER_CLICKHOUSE_TABLE`: target table for `JSONEachRow` inserts.
- `AI_LOGGER_SERVER_CHECK_TIMEOUT`: health-check timeout in seconds.

Graylog can be checked directly with:

```powershell
ai-logger-graylog-check
```

## Ask About Logs With DeepSeek

`ai-logger-log-query` reads one JSON Lines file or a directory of `*.jsonl`
files and asks DeepSeek to answer from the selected records:

```powershell
$env:DEEPSEEK_API_KEY = "<secret>"
ai-logger-log-query "What failed in the last run?" --logs-path "logs/projects"
```

For an offline context preview without calling DeepSeek:

```powershell
ai-logger-log-query "What failed?" --logs-path "logs/projects" --print-context
```

Optional variables:

- `AI_LOGGER_QUERY_LOGS_PATH`: default query log file or directory;
- `DEEPSEEK_BASE_URL`: default `https://api.deepseek.com`;
- `DEEPSEEK_MODEL`: default `deepseek-v4-flash`;
- `DEEPSEEK_TIMEOUT`: request timeout in seconds.

For local development, this repository also includes a Docker Compose Graylog
stack:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\graylog\start-graylog.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\graylog\create-gelf-http-input.ps1
```

## Architecture

`Logger` is the application-facing API. It accepts a message, severity, optional
context, exception details, and tags, then sends a normalized record to the
aggregator.

`LogAggregator` owns delivery. It can add static context, filter by minimum
level, buffer when plugins fail, and flush records to each registered plugin.

Plugins implement the `LogPlugin` protocol. Existing plugins:

- `DiskJsonLinesPlugin` writes one JSON object per line.
- `ProjectDailyJsonLinesPlugin` writes JSON Lines under
  `<root>/<project>/YYYY-MM-DD.jsonl`.
- `HttpJsonPlugin` sends JSON records over HTTP.
- `ServerHttpPlugin` sends records from project clients to the ai_logger server.
- `GraylogGelfPlugin` converts records to GELF for Graylog.
- `ClickHouseHttpPlugin` inserts records through ClickHouse HTTP
  `JSONEachRow`.
- `MemoryLogPlugin` is useful for tests and in-process inspection.

## Verification

```powershell
python -m unittest discover -s tests
```
