# Local ai_logger chain test config.
# This file contains no real secrets.

$env:AI_LOGGER_SERVER_HOST = "127.0.0.1"
$env:AI_LOGGER_SERVER_PORT = "8765"
Remove-Item Env:\AI_LOGGER_SERVER_JSONL_PATH -ErrorAction SilentlyContinue
$env:AI_LOGGER_SERVER_PROJECT_DAILY_DIR = "logs/projects"
$env:AI_LOGGER_SERVER_URL = "http://127.0.0.1:8765/ingest"
$env:AI_LOGGER_PROJECT = "ai-logger-chain-test"
$env:AI_LOGGER_SERVICE = "demo-client"
$env:AI_LOGGER_ENVIRONMENT = "local"
$env:AI_LOGGER_FALLBACK_JSONL_PATH = "logs/client-fallback.jsonl"
$env:AI_LOGGER_QUERY_LOGS_PATH = "logs/projects"
