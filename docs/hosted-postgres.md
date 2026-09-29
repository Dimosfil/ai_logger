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

The Node client in `clients/node/` needs only
`AI_LOGGER_SERVER_URL=https://<host>/ingest` and
`AI_LOGGER_PROJECT=ai-media-client`. It sends only selected diagnostic
fields and requires HTTPS for remote delivery. No files in
`ai-media-client` are changed by this repository.
