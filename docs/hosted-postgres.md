# Hosted PostgreSQL logger

The service accepts diagnostic records over HTTP, stores them in PostgreSQL,
and displays them at `/` and `/admin`. This initial deployment has no application
passwords or API keys. The `/ingest`, `/api/agent/logs`, `/admin`, and
existing web settings/search routes are open to anyone who can reach the
service. Add access control before sending sensitive logs.

## Configure

Set `DATABASE_URL` in the hosting platform's private environment. The Docker
image sets `AI_LOGGER_REQUIRE_POSTGRES=1` and fails to start without the URL.
The database account needs permission to create the `ai_logger_records` table
on first startup and to insert/select records afterward. No admin token,
client API key, or extra database is needed. A former
`ai_logger_api_keys` table, if present, is left untouched but is no longer
used.

Database TLS works like in `ai-media-client`: it is off by default and enabled
with `DATABASE_SSL=1`. The supplied endpoint does not support TLS, so its
`DATABASE_URL` needs no additional option. With the default setting, the
database password and log data travel unencrypted. Keep the URL out of Git and
support logs.

The application uses the platform's `PORT` when provided and binds to
`0.0.0.0`; the internal port configured in Bothost must match. For local
Compose, copy `.env.example` to ignored `.env`, set `DATABASE_URL`, and run
`docker compose up -d --build`. Compose uses `AI_LOGGER_SERVER_PORT` for both
the container and the loopback host port; there is no separate publish port.

## Use

- `GET /health` checks the database and returns 200 when ready.
- `POST /ingest` accepts one record or up to 100 records, with a 1 MiB body
  limit. Each record needs `context.project`. It returns 202 after storing
  selected records; a database failure returns 503.
- `GET /api/agent/logs?project=ai-media-client&levels=ERROR,WARNING&limit=100`
  returns recent records. `since=<ISO-8601>` is also supported. Maximum limit
  is 500.
- `GET /` and `GET /admin` show PostgreSQL records with project, level, and
  count filters. The existing JSONL journal is available at `/journal` when
  configured.

The time column shows `DD.MM.YYYY HH:mm:ss` in the browser's local timezone,
without fractional seconds or a timezone suffix. Hover over a time to see the
original timestamp with its full precision and timezone.
The “Машина” column displays `context.instance_id` from the sending client;
older records without it show an em dash. Configure `AI_LOGGER_INSTANCE_ID`
on each sender, using distinct permanent IDs for your PC, other PCs, and hosting.

The message column displays an error description, code, source file/line and
entity when supplied, plus an exception type and up to eight stack lines.
“Подробности” shows labeled role, environment, request/task IDs and other
selected metadata instead of raw JSON. Older event-only records show a
readable event/code label and explicitly indicate missing diagnostics.
Send exception type/message/stack_trace in the protocol's `exception` object;
optional `context.description/file/line/function/entity` provide source details.

The Node client in `clients/node/` needs only
`AI_LOGGER_SERVER_URL=https://<host>/ingest` and
`AI_LOGGER_PROJECT=ai-media-client`. It sends only selected diagnostic
fields and requires HTTPS for remote delivery. No files in
`ai-media-client` are changed by this repository.

## Telegram bot

The hosted process also runs `@ai_loggerbot` by long polling when it receives
`TELEGRAM_BOT_TOKEN` or Bothost's `BOT_TOKEN`. The Docker image expects the
Telegram username `ai_loggerbot` and checks it with `getMe` before polling. If
the token belongs to another bot, `/health` reports `telegram.error` as
`wrong_bot_token`. Only private `/start` and `/help` are handled for now; the
reply confirms that `ai_logger` is running. The bot needs outbound HTTPS to
Telegram and does not open another inbound port. Run only one instance with
the same token; another poller or an active webhook can cause `poll_conflict`.

Locally, put `TELEGRAM_BOT_TOKEN` in the ignored `.env`. Keep it out of Git.
`/health` reports bot configuration, thread state, and an error code separately
from database health. An unavailable Telegram API does not stop the log server.
