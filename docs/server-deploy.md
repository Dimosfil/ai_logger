# Server Deploy Guide

This guide is the contract for agents that deploy the `ai_logger` server on a
machine.

## Goal

Run one local/server process that accepts normalized records at `/ingest`,
exposes `/health`, and writes or forwards accepted records through configured
backend plugins.

## Deployment Shape

```text
project clients -> http://<host>:<port>/ingest -> ai_logger server -> backend plugins
```

The server is dependency-free Python. Graylog GELF HTTP is the first supported
centralized backend. JSON Lines remains useful as a local fallback or
development backend.

## Windows 10 Without Docker

For a Windows 10 machine where Docker is not available, use the prepared
agent-facing entrypoint:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\install.ps1
Copy-Item .\deploy\windows\env.example.ps1 .\deploy\windows\env.local.ps1
# Edit env.local.ps1 with machine-local values before starting.
powershell -ExecutionPolicy Bypass -File .\deploy\windows\start-server.ps1 -Background
powershell -ExecutionPolicy Bypass -File .\deploy\windows\check.ps1
```

The scripts install this repository into `.venv`, load machine-local settings
from `deploy\windows\env.local.ps1`, start `ai-logger-server`, and run health,
ingest, and Graylog checks.

This path prepares `ai_logger` on Windows. When no Graylog backend exists yet,
use the local Docker Compose Graylog stack under `deploy/graylog/`, or keep
`AI_LOGGER_SERVER_PROJECT_DAILY_DIR` enabled as a local fallback until Graylog is
ready.

## Local Graylog Backend

For local development with Docker available, start Graylog before configuring
the `ai_logger` server:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\graylog\start-graylog.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\graylog\create-gelf-http-input.ps1
powershell -ExecutionPolicy Bypass -File .\deploy\graylog\check-graylog.ps1
```

The local stack exposes:

- Graylog UI/API: `http://127.0.0.1:9000/`;
- GELF HTTP input: `http://127.0.0.1:12201/gelf`.

Then configure the `ai_logger` server:

```powershell
$env:AI_LOGGER_GRAYLOG_GELF_URL = "http://127.0.0.1:12201/gelf"
$env:AI_LOGGER_GRAYLOG_HOST = "ai-logger-local"
$env:AI_LOGGER_GRAYLOG_TIMEOUT = "5"
```

See `deploy/graylog/README.md` for stop commands, local credentials, and
private `.env` handling.

## Required Inputs

- Target machine and project folder.
- Python 3.9 or newer.
- Server bind host and port.
- Backend choice: Graylog GELF HTTP, JSONL fallback, ClickHouse HTTP, or a
  combination.
- Optional bearer token for `/ingest`.
- Writable log/output folder when JSONL is enabled.

## Agent Flow

1. Confirm the target machine, folder, host, port, and backend.
2. Install the package in the selected Python environment.
3. Configure server environment variables.
4. Start `ai-logger-server`.
5. Run `ai-logger-server-check`.
6. Run `ai-logger-client-check` against the same `/ingest` URL.
7. Verify the backend received the test event.
8. Record the selected URL, token source, and backend path in the target
   project's private deployment notes. Do not store raw secrets in shared docs.

For Windows 10 without Docker, prefer the scripts under `deploy/windows/` before
hand-running the generic commands below.

To stop a server started by `deploy\windows\start-server.ps1 -Background`, use:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\windows\stop-server.ps1
```

## Install

For development from a local checkout:

```powershell
python -m pip install -e <ai_logger_repo_path>
```

From Git:

```powershell
python -m pip install git+https://github.com/Dimosfil/ai_logger.git
```

## Configure Graylog Backend

Create, start, or choose a Graylog GELF HTTP input, then configure the server:

```powershell
$env:AI_LOGGER_SERVER_HOST = "127.0.0.1"
$env:AI_LOGGER_SERVER_PORT = "8765"
$env:AI_LOGGER_SERVER_TOKEN = "dev-secret"
$env:AI_LOGGER_GRAYLOG_GELF_URL = "http://graylog.example:12201/gelf"
$env:AI_LOGGER_GRAYLOG_HOST = "ai-logger-local"
$env:AI_LOGGER_GRAYLOG_TIMEOUT = "5"
```

Verify the Graylog input directly before routing project logs through the
server:

```powershell
ai-logger-graylog-check
```

Expected success output:

```text
ai_logger Graylog check delivered to http://graylog.example:12201/gelf
```

The Graylog payload uses GELF 1.1 fields:

- `short_message`: the `LogRecord.message`;
- `full_message`: stack trace, exception message, or the short message;
- `host`: context `host` or `AI_LOGGER_GRAYLOG_HOST`;
- `_logger`, `_record_id`, `_tags`, `_exception_type`, and context fields as
  GELF additional fields.

## Configure JSONL Backend

For multiple projects, prefer per-project daily files:

```powershell
$env:AI_LOGGER_SERVER_HOST = "127.0.0.1"
$env:AI_LOGGER_SERVER_PORT = "8765"
$env:AI_LOGGER_SERVER_TOKEN = "dev-secret"
$env:AI_LOGGER_SERVER_PROJECT_DAILY_DIR = "logs/projects"
```

Accepted records are written to:

```text
logs/projects/<project>/YYYY-MM-DD.jsonl
```

The legacy single-file backend is still available:

```powershell
$env:AI_LOGGER_SERVER_HOST = "127.0.0.1"
$env:AI_LOGGER_SERVER_PORT = "8765"
$env:AI_LOGGER_SERVER_TOKEN = "dev-secret"
$env:AI_LOGGER_SERVER_JSONL_PATH = "logs/server.jsonl"
```

`AI_LOGGER_SERVER_TOKEN` is optional, but recommended when clients outside the
same trusted local process can reach the server.

## Start

Foreground start:

```powershell
ai-logger-server
```

Background start on Windows:

```powershell
Start-Process -WindowStyle Hidden -FilePath "ai-logger-server"
```

If a process supervisor is used, configure it to run `ai-logger-server` with the
same environment variables. Keep secrets in the supervisor's private secret
store or machine-local environment, not in shared repository files.

## Health Check

```powershell
ai-logger-server-check
```

Equivalent HTTP check:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8765/health"
```

Expected response:

```json
{
  "status": "ok",
  "service": "ai_logger",
  "plugins": 1
}
```

## Ingest Check

```powershell
$env:AI_LOGGER_SERVER_URL = "http://127.0.0.1:8765/ingest"
$env:AI_LOGGER_PROJECT = "server-deploy-check"
$env:AI_LOGGER_SERVICE = "agent"
$env:AI_LOGGER_SERVER_TOKEN = "dev-secret"
ai-logger-client-check
```

For a JSONL backend, verify the file has a test event:

```powershell
$today = Get-Date -Format "yyyy-MM-dd"
Get-Content -LiteralPath "logs/projects/server-deploy-check/$today.jsonl" -Tail 5
```

For a Graylog backend, search Graylog for:

```text
short_message:ai_logger.client_check OR short_message:ai_logger.graylog_check
```

## Query Logs With DeepSeek

After JSONL logging is enabled and events exist in the file, ask DeepSeek about
the logs:

```powershell
$env:DEEPSEEK_API_KEY = "<secret>"
ai-logger-log-query "What happened in the last run?" --logs-path "logs/projects"
```

For local verification without an LLM call:

```powershell
ai-logger-log-query "What happened?" --logs-path "logs/projects" --print-context
```

## Backend Variables

- `AI_LOGGER_SERVER_JSONL_PATH`: writes accepted records as JSON Lines.
- `AI_LOGGER_SERVER_PROJECT_DAILY_DIR`: writes accepted records to
  `<dir>/<project>/YYYY-MM-DD.jsonl`.
- `AI_LOGGER_GRAYLOG_GELF_URL`: forwards accepted records to a Graylog GELF HTTP
  input.
- `AI_LOGGER_GRAYLOG_HOST`: GELF `host` value.
- `AI_LOGGER_GRAYLOG_TIMEOUT`: Graylog request timeout in seconds.
- `AI_LOGGER_CLICKHOUSE_URL`: ClickHouse HTTP endpoint.
- `AI_LOGGER_CLICKHOUSE_TABLE`: target table for `JSONEachRow` inserts.
- `AI_LOGGER_CLICKHOUSE_TIMEOUT`: ClickHouse request timeout in seconds.

## Stop / Restart

If started in foreground, stop with `Ctrl+C`.

If started by a supervisor, use that supervisor's documented stop/restart
command. Do not kill unrelated Python processes by name. Match the process by
command line, working directory, and configured port before stopping it.

## Success Criteria

- `/health` returns `status: ok`.
- `/health` includes `graylog_gelf` in `plugin_names` when Graylog is enabled.
- `ai-logger-graylog-check` exits with code `0` when Graylog is enabled.
- `ai-logger-client-check` exits with code `0`.
- The configured backend contains the test event.
- Existing machine secrets are not printed, committed, or copied into shared
  documentation.
