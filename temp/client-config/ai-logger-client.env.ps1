# Temporary ai_logger client connection config.
# Copy or source these values in the target client project and replace placeholders.

$env:AI_LOGGER_SERVER_URL = "http://192.168.3.63:8765/ingest"
$env:AI_LOGGER_PROJECT = "ai_logger"
$env:AI_LOGGER_SERVICE = "codex-agent"
$env:AI_LOGGER_ENVIRONMENT = "dev"
$env:AI_LOGGER_HTTP_TIMEOUT = "5"
$env:AI_LOGGER_FALLBACK_JSONL_PATH = "logs/ai_logger_fallback.jsonl"

# Set AI_LOGGER_SERVER_TOKEN separately only when the ai_logger server requires bearer auth.
# Do not commit real tokens or placeholder bearer values.
