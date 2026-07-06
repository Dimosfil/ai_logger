# Copy this file to env.local.ps1 on the target machine and edit the values.
# Keep env.local.ps1 private; do not commit real tokens or private endpoints.

$env:AI_LOGGER_SERVER_HOST = "127.0.0.1"
$env:AI_LOGGER_SERVER_PORT = "8765"

# Optional but recommended when clients are not strictly local-only.
$env:AI_LOGGER_SERVER_TOKEN = "change-me"

# Graylog GELF HTTP input. Example: http://graylog.example:12201/gelf
$env:AI_LOGGER_GRAYLOG_GELF_URL = "http://127.0.0.1:12201/gelf"
$env:AI_LOGGER_GRAYLOG_HOST = "ai-logger-windows"
$env:AI_LOGGER_GRAYLOG_TIMEOUT = "5"

# Local fallback accepted by ai_logger even when Graylog is unavailable.
$env:AI_LOGGER_SERVER_JSONL_PATH = "logs\server.jsonl"

# Client check target used by check.ps1.
$env:AI_LOGGER_SERVER_URL = "http://127.0.0.1:8765/ingest"
$env:AI_LOGGER_PROJECT = "server-deploy-check"
$env:AI_LOGGER_SERVICE = "windows-agent"
