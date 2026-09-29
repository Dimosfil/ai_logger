# Hosted PostgreSQL logger

This deployment adds durable PostgreSQL records and scoped API keys to the
existing `/ingest` server. PostgreSQL is the authoritative ingest store when
`DATABASE_URL` is set. JSONL remains a local browsing/fallback copy. The
database URL is for **ai_logger**; client projects keep separate credentials.

## Configure

Copy `.env.example` to ignored `.env` and set:

- `DATABASE_URL`: PostgreSQL connection string for the logger database;
- `AI_LOGGER_ADMIN_TOKEN`: long random secret used only by the administrator;
- `AI_LOGGER_SERVER_PROJECT_DAILY_DIR=/app/logs`: JSONL copy for the existing web viewer.

PostgreSQL TLS is required by the server (`sslmode=require`). The currently
supplied database endpoint on port 16173 answered without SSL in the
2026-09-29 connectivity check, so the container must remain stopped until a
TLS-enabled endpoint or secure tunnel is configured. Its tables were created
before that limitation was discovered; no live logger should use plain TCP.

Start with `docker compose up -d --build`. On startup, the server creates
`ai_logger_records` and `ai_logger_api_keys` if absent. The connection account
needs DDL permission on first startup and DML permission afterward. Check
`http://127.0.0.1:8765/health` (or `AI_LOGGER_PUBLISH_PORT` if changed).
Compose binds only to loopback. For remote
clients, place an HTTPS reverse proxy in front and route `/ingest` and read
endpoints to this service. Set the client's `AI_LOGGER_SERVER_URL` to that
public HTTPS `/ingest` address.
`/health` returns 503 if PostgreSQL cannot be reached.

## Key management

Open `/admin`, enter `AI_LOGGER_ADMIN_TOKEN`, and issue a key. A client key
needs `ingest`; an agent key needs `read`. One key may have both scopes, though
separate keys make independent revocation possible. Bind keys to a project
(for example `ai-media-client`) to prevent cross-project send or read access.
The full key appears only at creation. The database stores a SHA-256 digest,
prefix, scope, project, and revocation time. Revoke compromised or retired keys
in `/admin`. Keep the bootstrap admin token and issued keys outside Git.

## API

All calls use `Authorization: Bearer <key>`. `POST /ingest` accepts the existing
protocol (one record or up to 100 records, 1 MiB maximum); each record needs
`context.project`. The server writes selected records to PostgreSQL before
returning 202. A PostgreSQL failure returns 503, so clients can retry or use
their local fallback. Duplicate `(project, id)` records are ignored.

`GET /api/agent/logs?project=ai-media-client&levels=ERROR,WARNING&limit=100`
returns `{"records":[...]}` newest first. `since=<ISO-8601>` limits the
earliest timestamp. A project-bound read key cannot request another project.
The administrator can use the existing web viewer at `/`; it prompts for the
bootstrap token when it loads data. Collection settings and web search are
administrator-only. `/health` remains public for health checks.

The existing `ai-media-client` system-error rows are not copied automatically.
Only sanitized new events should enter `/ingest`; account journals, prompts,
cookies, tokens, and raw provider responses stay in the owning application.
