# Local Graylog Deployment

This folder provides a local Docker Compose Graylog backend for `ai_logger`.
It is intended for development and agent verification, not as a hardened
production Graylog installation.

The stack contains:

- Graylog Open `7.1`;
- MongoDB `6.0.18`;
- OpenSearch `2.15.0`.

Ports:

- Graylog UI/API: `http://127.0.0.1:9000/`;
- GELF HTTP input: `http://127.0.0.1:12201/gelf`.

## Start

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\graylog\start-graylog.ps1
```

The script creates `deploy\graylog\.env` when missing. That file contains local
password material and is ignored by Git.

After Graylog starts, create the GELF HTTP input:

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\graylog\create-gelf-http-input.ps1
```

Default local UI credentials created by the start script:

```text
admin / admin
```

Change them in `deploy\graylog\.env` for anything beyond a disposable local
environment.

## Check

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\graylog\check-graylog.ps1
```

Configure the `ai_logger` server to forward accepted records to Graylog:

```powershell
$env:AI_LOGGER_GRAYLOG_GELF_URL = "http://127.0.0.1:12201/gelf"
$env:AI_LOGGER_GRAYLOG_HOST = "ai-logger-local"
$env:AI_LOGGER_GRAYLOG_TIMEOUT = "5"
```

## Stop

```powershell
powershell -ExecutionPolicy Bypass -File .\deploy\graylog\stop-graylog.ps1
```

Data is stored in Docker named volumes. Do not delete volumes unless you intend
to remove the local Graylog data.

