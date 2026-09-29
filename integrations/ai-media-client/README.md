# AI Media Client integration package

This directory stages the `ai-media-client` side of the logging integration.
It is separate from the `ai_logger` HTTP/PostgreSQL backend and from the
`@ai_loggerbot` Telegram bot, both of which run in this repository's server.
The two source files mirror the integration already present in the sibling
project as of 2026-09-29; that project was not edited to make this package.

## Transfer

Copy `src/ai-logger-client.mjs` and `src/ai-logger.js` into the target
project's `src/` directory. The backend should set
`AI_LOGGER_SERVER_URL=https://ailogger.bothost.tech/ingest` and may set
`AI_LOGGER_SERVICE` to a role such as `web` or `executor`.
`AI_LOGGER_ENVIRONMENT` and `AI_LOGGER_FALLBACK_JSONL_PATH` are optional.
The package's `.env.example` shows the service variables; the logger server
itself needs its own `DATABASE_URL` and Telegram token in its private environment.
Do not copy database credentials or the Telegram token into the client.

The current media client already calls `reportLifecycle(event)` from
`src/generation-log.js` and `reportSystemError(row)` from
`src/system-errors.js`. These hooks select short event names, source, and
error code. They do not forward prompts, media, provider payloads, account
IDs, or raw error descriptions. Its local `media_system_errors` table remains
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
