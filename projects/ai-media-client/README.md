# AI Media Client integration package

This is the consumer-specific workspace for `ai-media-client`, whose source
repository is `D:\AI\ai-media-client`. The logger backend is maintained in this
repository; the consumer source remains unchanged by this package move.

Hosted base URL: `https://ailogger.bothost.tech`.
Project identifier: `ai-media-client`.

## Directory contents

- `src/`, `test/`: the consumer's transferable integration and its tests.
- `.env.example`: non-secret hosted forwarding configuration.
- [Agent switch prompt](AGENT_SWITCH_PROMPT.md): instructions for the agent
  responsible for switching the consumer to hosted logging.
- Shared client and extracted error recorder:
  [clients/node](../../clients/node/README.md).

The public `/ingest` stores records in `ai_logger_records`; the extracted
private `ai_logger_system_errors` schema is opt-in and is not wired to that
HTTP endpoint. Complete error-store replacement remains pending. Keep the
consumer's local error table and readers until the replacement is verified.

This directory stages the `ai-media-client` side of the logging integration.
It is separate from the `ai_logger` HTTP/PostgreSQL backend and from the
`@ai_loggerbot` Telegram bot, both of which run in this repository's server.
The two source files mirror the integration already present in the sibling
project as of 2026-09-29; these are transfer snapshots rather than the
authoritative shared client. That project was not edited to make this package.

## Transfer

Copy `src/ai-logger-client.mjs` and `src/ai-logger.js` into the target
project's `src/` directory. The backend should set
`AI_LOGGER_SERVER_URL=https://ailogger.bothost.tech/ingest` and may set
`AI_LOGGER_SERVICE` to a role such as `web` or `executor`.
`AI_LOGGER_ENVIRONMENT` and `AI_LOGGER_FALLBACK_JSONL_PATH` are optional.
Set `AI_LOGGER_INSTANCE_ID` to a permanent machine label such as `my-pc`,
`friend-pc`, or `bothost`. Pass it into each sending container and retain it
across restarts/recreation; `AI_LOGGER_SERVICE` continues to identify the role.
The transfer client now sends `context.instance_id`; update the consumer's
copied client and forwarder before expecting this field in live records.
The package's `.env.example` shows the service variables; the logger server
itself needs its own `DATABASE_URL` and Telegram token in its private environment.
Do not copy database credentials or the Telegram token into the client.

Agent read path after successful delivery:
`GET https://ailogger.bothost.tech/api/agent/logs?project=ai-media-client&levels=ERROR,WARNING&limit=100`.
Check `/health`, send a safe uniquely identifiable event and read it back
before claiming that hosted forwarding works. The hosting dashboard's status
does not by itself verify delivery or persistence.

The current media client already calls `reportLifecycle(event)` from
`src/generation-log.js` and `reportSystemError(row)` from
`src/system-errors.js`. These hooks select short event names, source, and
error code. The updated transfer forwarder also accepts selected
`row.diagnostic` fields (description, file, line, function, entity) and
`row.exception` (type, message, stack_trace). It does not copy arbitrary
`row.message` or `row.details`. Update the consumer to supply these fields
from its error capture; existing event-only rows cannot recover a stack.
Prompts, media, provider payloads and account IDs remain excluded.
Its local `media_system_errors` table remains
application-owned until a separate migration is planned.

## Components

- `src/ai-logger-client.mjs`: HTTP client, field allowlist, sanitization,
  timeout, and optional local JSONL fallback.
- `src/ai-logger.js`: media-client-specific asynchronous forwarder for
  generation lifecycle and system error metadata.
- `test/ai-logger.test.js`: verifies filtering and failure isolation. Run with
  `node --test test/ai-logger.test.js` from this directory.

`@ai_loggerbot` is deployed with the logger backend. It uses the same service
process and a single outbound long poll; no Telegram module is required in the
media client for logging. The media client's own Telegram generation bot is a
separate application and remains in its project.
