# Agent Install Guide

This guide is the contract for project agents that need to install `ai_logger`
into another project.

## Goal

Install the smallest native adapter that fits the target project's logging
framework, send normalized records to the ai_logger ingest protocol, and verify
that a test event reaches the server.

## Agent Flow

1. Confirm the target project root and stack before editing files.
2. Inspect the target project's logging framework and startup/configuration
   entry points.
3. Read `docs/adapter-manifest.json` and choose the matching implemented
   adapter.
4. Install the package in the target project.
5. Configure `AI_LOGGER_SERVER_URL`, `AI_LOGGER_PROJECT`, and
   `AI_LOGGER_SERVICE`.
6. Configure optional values when available: token, environment, host, timeout,
   and fallback JSON Lines path.
7. Add the native adapter without replacing the project's existing logging
   behavior unless the user explicitly asks for replacement.
8. Run `ai-logger-client-check` from the target project environment.
9. Verify the ai_logger server accepted the event or inspect the configured
   fallback JSON Lines file when delivery failed.

## Python Logging Adapter

Install from a local checkout during development:

```powershell
python -m pip install -e <ai_logger_repo_path>
```

Install from Git when the repository is reachable:

```powershell
python -m pip install git+https://github.com/Dimosfil/ai_logger.git
```

Configure the target project's environment:

```powershell
$env:AI_LOGGER_SERVER_URL = "http://127.0.0.1:8765/ingest"
$env:AI_LOGGER_PROJECT = "target-project"
$env:AI_LOGGER_SERVICE = "worker"
$env:AI_LOGGER_ENVIRONMENT = "dev"
$env:AI_LOGGER_FALLBACK_JSONL_PATH = "logs/ai_logger_fallback.jsonl"
```

Use `AI_LOGGER_SERVER_TOKEN` when the server requires bearer auth.

Add the handler in the project's logging setup:

```python
import logging

from ai_logger import configured_logging_handler

logging.getLogger("target-project.worker").addHandler(configured_logging_handler())
```

Or configure it explicitly:

```python
import logging

from ai_logger import AiLoggerClientOptions, AiLoggerHttpHandler

handler = AiLoggerHttpHandler(
    options=AiLoggerClientOptions(
        server_url="http://127.0.0.1:8765/ingest",
        token=None,
        project="target-project",
        service="worker",
        environment="dev",
        fallback_jsonl_path="logs/ai_logger_fallback.jsonl",
    )
)

logging.getLogger("target-project.worker").addHandler(handler)
```

Verify installation:

```powershell
ai-logger-client-check
```

Expected success output:

```text
ai_logger client check delivered to http://127.0.0.1:8765/ingest
```

## Adapter Selection Rules

- Use `python.logging` when the project uses Python standard `logging`.
- For Python projects using `structlog` or `loguru`, bridge those frameworks to
  the Python handler or implement a native sink that delegates to
  `AiLoggerClient`.
- For ASP.NET Core and other planned stacks, do not invent one-off HTTP calls
  in application code. Add or implement the native adapter shape recorded in
  `docs/adapter-manifest.json` first.

## Verification Checklist

- A test event reaches the ai_logger server `/ingest`.
- The target project's existing logs still behave as before.
- Secret-like fields are redacted in outgoing payloads.
- Server outages do not crash the target application path.
- Fallback JSON Lines output is configured when local durability is required.
