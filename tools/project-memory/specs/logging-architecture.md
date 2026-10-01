# Logging Architecture

Last reviewed: 2026-09-29

## Goal

Provide a universal client/server logging system for `ai_logger` that can be
connected to projects on different stacks through native client adapters and
run separately as a local server process.

Success criteria:

- application code logs through a stable abstraction;
- project clients can be Python handlers, NLog targets, log4net appenders,
  Serilog sinks, pino transports, or other native logging adapters;
- every adapter sends normalized records to the ai_logger ingest server;
- the server can route accepted records to selected backend systems;
- an aggregator receives, enriches, filters, and fan-outs records;
- logging destinations are replaceable plugins;
- disk, per-project daily JSONL, HTTP, Graylog GELF, and ClickHouse-oriented
  plugins are available;
- a local web UI can browse stored JSONL logs by project, file, and level;
- exception logging can be applied with a context manager or decorator;
- plugin failures do not crash the application path by default.

## Layers

The opt-in Node.js system-error recorder is extracted from the temporary media
client implementation. Its private, project-scoped PostgreSQL schema and
queue/sanitizer/retention contract are documented in
[system-error-recorder.md](system-error-recorder.md). The source application's
table remains active; the new private table is not used by the public ingest
server and is installed only explicitly by its owner.

```mermaid
flowchart LR
  App["Project application"] --> NativeLogger["Native logging framework"]
  NativeLogger --> ClientAdapter["ai_logger client adapter"]
  ClientAdapter --> ServerHttp["HTTP ingest protocol"]
  ServerHttp --> Ingest["ai_logger server /ingest"]
  Ingest --> ServerAggregator["Server LogAggregator"]
  ServerAggregator --> Disk["DiskJsonLinesPlugin"]
  ServerAggregator --> Graylog["GraylogGelfPlugin"]
  ServerAggregator --> ClickHouse["ClickHouseHttpPlugin"]
  ServerAggregator --> Other["Custom backend plugins"]
  Ingest --> WebUi["Web UI and read API"]
  WebUi --> StoredLogs["JSONL log files"]
```

## Hosted PostgreSQL workflow (current)

When `DATABASE_URL` is set, startup creates the `ai_logger_records` table.
The database URL is a private environment value. The records table stores
normalized protocol JSON plus project, record ID, level, logger, and
timestamps. `(project, record_id)` is unique for retry deduplication.
The Docker image sets `AI_LOGGER_REQUIRE_POSTGRES=1` and requires the database
URL before starting. An existing `ai_logger_api_keys` table is not dropped but
is no longer created or used.
Database TLS follows the same configuration as `ai-media-client`: plain TCP by
default, `DATABASE_SSL=1` to require TLS. The supplied endpoint lacks TLS, so
the user-approved URL works without an extra variable. In the default mode,
database credentials and log records are unencrypted on the database link.

The hosted service currently has no HTTP authentication. `/ingest`,
`/api/agent/logs`, `/`, `/admin`, and the existing JSONL browser/settings/search
routes are open. `/` and `/admin` display PostgreSQL records; `/journal`
displays the local JSONL copy when configured. No key issue or revoke routes
are exposed.
The PostgreSQL admin level filter uses native checkboxes for DEBUG, INFO,
WARNING, ERROR and CRITICAL. Selected levels are joined with commas in the
existing `levels` query parameter (OR matching). Changes reload the table;
“Все” clears the selection and no selection omits `levels`, showing all levels.
Project and count filters compose with this selection. Implementation:
`src/ai_logger/admin.py`; contract coverage: `tests/test_hosted_server.py`
(checked 2026-10-01).

The PostgreSQL table UI formats timestamps as `DD.MM.YYYY HH:mm:ss` in the
browser's local timezone, with seconds but no fractional seconds or offset.
The original timestamp is preserved in the time cell's hover title; missing
values show an em dash and invalid dates retain their source text. Stored
records and API timestamp serialization are unchanged. Implementation:
`src/ai_logger/admin.py` (checked 2026-09-30).
`/health` reports storage unavailable with HTTP 503 when PostgreSQL cannot be
reached. The public access policy is deliberate for the initial deployment;
records must be sanitized before sending.
For hosted routing, a platform `PORT` takes precedence over
`AI_LOGGER_SERVER_PORT`; when `PORT` is present and no explicit host is set,
the process binds to `0.0.0.0`. Local default remains `127.0.0.1:8766`.

On `POST /ingest`, validate batch size, protocol records, and required
`context.project` before writing. Store all selected records in one PostgreSQL
transaction, then emit to optional JSONL/other plugins and return 202. A
storage failure returns 503 so the client can retry; plugin copies are
best-effort after the authoritative database write. The agent reads bounded,
newest-first records from `/api/agent/logs` with project, level, and time
filters. The portable Node.js client in `clients/node/` permits only named
diagnostic context fields and returns a failure result or writes a local
fallback when the server is unreachable.
The Node.js client uses no API key and rejects remote HTTP URLs; loopback HTTP
is allowed for local development.

The `ai-media-client` source already contains forwarding hooks; actual hosted
delivery has not been verified in this task. Its `media_system_errors` and
generation/account journals remain application-owned. The central logger
receives selected diagnostic metadata; full error-store replacement is pending.
`projects/ai-media-client/` is the transfer package for the existing
Node client and media-specific forwarder. The backend and Telegram bot remain
in `ai_logger`. The bot uses private-chat long polling with the configured
Telegram token and responds to `/start` and `/help`; it has no access to media
tasks or log records yet. `getMe` must identify `ai_loggerbot` before polling.
Current implementation evidence: `src/ai_logger/server.py`,
`src/ai_logger/postgres_store.py`, `src/ai_logger/admin.py`,
`src/ai_logger/telegram_bot.py`, `clients/node/ai-logger-client.mjs`,
`projects/ai-media-client/`, `tests/test_hosted_server.py`, and
`docs/hosted-postgres.md` (checked 2026-09-29).

## Contracts

### Readable error diagnostics (implemented 2026-09-30)

Admin records display description (context.description, then exception.message),
or a readable known-event label with the original event retained. Known code
labels describe only the reported category, never infer an exact root cause.
File/module, line, function, entity, exception type and a bounded eight-line
stack fragment are shown when present. Python traceback fragments keep the
last eight lines; other stacks keep the first eight. Missing error descriptions
and stacks are stated explicitly, with no invented source location.
Selected scalar metadata is rendered as labeled details, never raw context JSON.
All supplied content uses textContent, including stack and descriptions.

Node clients accept optional exception type/message/stack_trace (or Error
name/message/stack), bounded to 100/1000/4000 characters. Context allowlists
description (1000), file/line/function/entity (200 each). Existing credential
redaction applies; URL credentials/query/fragment are stripped from diagnostic
strings. Python logging adds source pathname to existing line/function metadata
and already serializes exceptions. Storage/read APIs use the existing context
and exception contract without a migration.
The media transfer package forwards explicit row.diagnostic fields and
row.exception, excluding arbitrary row.message/details. Its live consumer
requires an update before sending these fields; old records are not backfilled.
Evidence: `src/ai_logger/admin.py`, `src/ai_logger/logging_adapter.py`,
`clients/node/ai-logger-client.mjs`, `clients/node/system-errors.mjs`,
`tests/test_admin_ui.py`, Node client/recorder/transfer tests.

### Source machine identity (implemented 2026-09-30)

The optional `context.instance_id` identifies a sender's machine or hosting
installation. Node.js and Python clients read `AI_LOGGER_INSTANCE_ID` from
their configuration; direct construction accepts `instanceId` and
`instance_id`, respectively. A nonblank configured value is trimmed and added
to every outgoing record, including fallback delivery. Event context cannot
override it. An unset/blank value does not generate a hostname or random ID.
Node.js applies its existing 200-character diagnostic-field sanitization.
Deployment owns uniqueness and persistence: roles on one machine share its
configured ID, other machines use different IDs, and container recreation
retains the configuration. `service` remains the process role and
`environment` remains the environment. No `run_id` or storage migration is
required. Ingest and read APIs retain the field as ordinary record context;
the PostgreSQL admin table displays it in “Машина”, or an em dash when absent.
Old stored records are not backfilled.

Evidence: `clients/node/ai-logger-client.mjs`,
`src/ai_logger/client.py`, `src/ai_logger/config.py`,
`src/ai_logger/admin.py`, `projects/ai-media-client/src/`,
`clients/node/ai-logger-client.test.mjs`, and `tests/test_client_adapters.py`.
The consumer package stages updated client/forwarder files; the external
consumer repository and its private deployment configuration were not changed.

Served consumers are organized under `projects/<project-id>/`. Each directory
owns consumer-specific adapters, tests, public configuration examples and
rollout instructions; [projects/README.md](../../../projects/README.md) indexes
them. Shared SDKs remain under `clients/`, backend runtime under `src/ai_logger/`,
and durable behavior contracts under project memory. This organization is
implemented as of 2026-09-30; moving integration files does not change runtime
behavior or modify external source repositories.

`Logger` is the public application API. It creates structured `LogRecord`
instances from severity, message, context, tags, and optional exception data.

`LogAggregator` is the delivery coordinator. It adds default context, applies a
minimum severity filter and custom filters, then emits each record to registered
plugins.

Client adapters are stack-specific bridges. A Python project may use
`AiLoggerHttpHandler`; .NET can use an ASP.NET Core `ILoggerProvider`, NLog
target, log4net appender, or Serilog sink; Node.js can use a pino or winston
transport. All adapters send the same normalized ingest protocol.

`AiLoggerClient` is the framework-neutral client core used by native adapters.
It owns ingest delivery, bearer-token authorization, default context enrichment,
common secret-field redaction, optional JSON Lines fallback, and delivery
failure tracking. Native adapters should convert framework events into
`LogRecord` or protocol dictionaries and delegate delivery to this client core
instead of duplicating HTTP behavior.

Project agents install adapters through the documented adapter manifest and
install guide. `docs/adapter-manifest.json` is the machine-readable adapter
selection contract, and `docs/agent-install.md` is the human-readable
installation workflow. The first implemented verification entry point is
`ai-logger-client-check`, which sends `ai_logger.client_check` to the configured
server and returns a non-zero exit code when delivery fails.

Project agents deploy the server through the documented server deploy manifest
and deploy guide. `docs/server-deploy-manifest.json` is the machine-readable
server deployment contract, and `docs/server-deploy.md` is the human-readable
machine deployment workflow. The server verification entry point is
`ai-logger-server-check`, which checks `/health` and returns a non-zero exit
code when the server is unavailable or unhealthy.

Graylog GELF HTTP was the first centralized server backend implementation.
`GraylogGelfPlugin` converts accepted `LogRecord` instances to GELF 1.1 and
sends them to `AI_LOGGER_GRAYLOG_GELF_URL`. `ai-logger-graylog-check` sends a
direct `ai_logger.graylog_check` GELF event so an agent can verify the Graylog
input before routing project traffic through the ai_logger server.

When no external Graylog backend exists, agents can start the project-local
Docker Compose backend from `deploy/graylog/`. That stack runs Graylog Open,
MongoDB, and OpenSearch, exposes the UI/API at `http://127.0.0.1:9000/`, and
exposes the GELF HTTP input at `http://127.0.0.1:12201/gelf` after
`deploy/graylog/create-gelf-http-input.ps1` creates the input. Local Graylog
password material belongs in ignored `deploy/graylog/.env`, not in committed
docs or project memory.

`ProjectDailyJsonLinesPlugin` is the preferred local fallback when multiple
projects send logs to one ai_logger server. It writes records under
`<root>/<project>/YYYY-MM-DD.jsonl`, using the `context.project` value when
present and a sanitized logger-name fallback otherwise. `AI_LOGGER_SERVER_JSONL_PATH`
remains available for a single historical file, and both sinks may be enabled
together when duplicate local storage is intentional.

`ai-logger-log-query` is the first LLM inspection surface. It reads JSON Lines
records from one file or a directory of `*.jsonl` files. Its default path is
`AI_LOGGER_QUERY_LOGS_PATH`, `AI_LOGGER_SERVER_PROJECT_DAILY_DIR`,
`AI_LOGGER_SERVER_JSONL_PATH`, or `logs/server.jsonl`. It compacts recent
records and asks DeepSeek through the OpenAI-compatible `/chat/completions` API.
It must not print or store `DEEPSEEK_API_KEY`; missing keys are reported as a
configuration blocker. The CLI also supports `--print-context` for offline
verification without an LLM call.

The server web UI is the first browser inspection surface. `LogIngestHttpServer`
serves the UI at `/`, project/file/level metadata at `/api/overview`, recent
records at `/api/logs`, and natural-language search at `/api/search`. The UI
reads JSON Lines logs from `AI_LOGGER_WEB_LOGS_ROOT`, then falls back through
`AI_LOGGER_QUERY_LOGS_PATH`, `AI_LOGGER_SERVER_PROJECT_DAILY_DIR`,
`AI_LOGGER_SERVER_JSONL_PATH`, and `logs`. Project folders follow the
`ProjectDailyJsonLinesPlugin` layout: `<root>/<project>/YYYY-MM-DD.jsonl`.
The `/api/logs` read order is newest first, with later records from the same
timestamp displayed above earlier records.
The web UI exposes persisted collection settings at `/api/settings`. Settings
are stored next to the configured web log root in `.ai_logger_settings.json` and
survive server restarts. `collect_levels` is a per-level boolean map for
`DEBUG`, `INFO`, `WARNING`, `ERROR`, and `CRITICAL`; disabled levels are not
accepted from `/ingest` and are excluded from read/search APIs. These settings
control collection, while the level buttons above the log table remain a
display filter for the current view.
When no DeepSeek key is configured, `/api/search` must keep working through
bounded local candidate ranking and return a warning instead of exposing or
requesting a secret in the browser.
The web search response is a two-part inspection result: `summary` is the bot
answer shown above the table, and `matches` are the supporting log rows shown
below it. When text ranking finds no local candidates but recent records exist
for the selected project/file/level scope, `/api/search` may send those recent
records to the configured LLM provider so questions such as "what broke in this
bot?" still receive an evidence-backed answer instead of stopping at an empty
local search result.
When a browser user asks AI from a visually filtered view, the server must still
include enabled `WARNING`, `ERROR`, and `CRITICAL` records in the analysis
scope. The UI display filter must not hide new errors, problems, or crashes
from `/api/search`; only explicitly disabled collection levels may exclude
those records.

`LogIngestHttpServer` is the server-side entry point. It accepts JSON
`LogRecord` payloads at `/ingest`, optionally verifies a bearer token, restores
records, and emits them into the server aggregator. It also exposes `/health`
for machine deployment checks and the browser UI/read API. `/health` reports
plugin count and plugin names so an agent can confirm that `graylog_gelf` is
enabled.

`LogPlugin` implementations own delivery details. A plugin may write to disk,
send over the network, keep records in memory, or adapt records to another
logging backend.

Plugin delivery failures are captured in `LogAggregator.failed_records` and are
reported to the configured error stream. They are intentionally not re-raised
from the application logging path.

## Current Implementation Map

- Core API: `src/ai_logger/logger.py`
- Aggregation: `src/ai_logger/aggregator.py`
- Records and levels: `src/ai_logger/records.py`, `src/ai_logger/levels.py`
- Plugins: `src/ai_logger/plugins.py`
- Environment configuration: `src/ai_logger/config.py`
- Exception helpers: `src/ai_logger/context.py`
- Tool/component logger helper: `src/ai_logger/tool_logging.py`
- Client core: `src/ai_logger/client.py`
- Python logging adapter: `src/ai_logger/logging_adapter.py`
- Server ingest: `src/ai_logger/server.py`
- Server web UI and read repository: `src/ai_logger/web.py`
- Client install check: `src/ai_logger/client_check.py`
- Server health check: `src/ai_logger/server_check.py`
- Graylog backend check: `src/ai_logger/graylog_check.py`
- LLM provider boundary: `src/ai_logger/llm.py`,
  `src/ai_logger/log_search_providers.py`
- Smart log search: `src/ai_logger/log_search.py`,
  `src/ai_logger/log_search_cli.py`
- LLM log query: `src/ai_logger/log_query.py`
- Protocol documentation: `docs/ingest-protocol.md`
- LLM search documentation: `docs/llm-log-search.md`
- Adapter documentation: `docs/client-adapters.md`
- Agent install documentation: `docs/agent-install.md`
- Adapter manifest: `docs/adapter-manifest.json`
- Server deploy documentation: `docs/server-deploy.md`
- Server deploy manifest: `docs/server-deploy-manifest.json`
- Local Graylog deployment: `deploy/graylog/README.md`,
  `deploy/graylog/docker-compose.yml`
- Verification: `tests/test_logging_core.py`,
  `tests/test_client_server.py`, `tests/test_client_adapters.py`,
  `tests/test_client_check.py`, `tests/test_server_check.py`,
  `tests/test_graylog_check.py`, `tests/test_log_search.py`,
  `tests/test_log_query.py`

## LLM Log Search Contract

Smart log search is a read-side analysis layer over collected server-side logs.
It must not replace the ingest protocol or backend plugin model.

The first implementation reads JSON Lines logs from a configured local file,
keeps only a bounded recent window, ranks candidate records locally, then sends
only the bounded candidate set to an LLM provider. This keeps large log files
out of provider requests and gives deterministic fallback behavior when the LLM
is unavailable.

Codex app-server is the default provider, using model
`gpt-codex-spark-high` unless `AI_LOGGER_CODEX_MODEL` or `CODEX_MODEL`
overrides it. The search layer also supports the reusable `llm_providers`
provider naming contract: `codex`, `deepseek`, `openai-compatible`, `mock`,
`local`, and `none`. DeepSeek keys are read from `DEEPSEEK_API_KEY` or
`AI_LOGGER_DEEPSEEK_API_KEY`; generic OpenAI-compatible keys are read from
`AI_LOGGER_LLM_API_KEY` or `LLM_API_KEY`. Keys must not be persisted in source,
documentation examples, project memory, logs, or search output. Model, base
URL, timeout, thinking mode, token cap, candidate count, top-K, and JSONL path
are configuration values, not code constants.

Provider integration is behind `LogSearchLlmProvider`. Future providers should
implement the same query/candidate analysis contract and preserve the local
candidate-ranking fallback.

The web UI natural-language search box uses the same provider registry as the
CLI. Users can leave provider selection on automatic environment-driven routing
or choose `codex`, `deepseek`, `openai-compatible`, `mock`, or `local` for a single
`/api/search` request. Search responses include the actual provider, warnings,
selected records, scores, and LLM/local reasons so the answer remains
evidence-backed.

### Related Provider Logic Source

`D:\AI\llm_providers` is registered as a connected project and reusable logic
source for smart-search provider refactoring. Its portable contracts are mapped
in
`tools/project-memory/specs/integration-contracts/llm-providers-logic-map.md`.
The first adoption keeps `ai_logger`'s log-search domain contract, candidate
redaction, record-id validation, and local fallback behavior as the caller-owned
layer while moving generic provider selection, transport configuration, mock
behavior, and JSON output parsing behind `src/ai_logger/log_search_providers.py`
and the stdlib clients in `src/ai_logger/llm.py`.
