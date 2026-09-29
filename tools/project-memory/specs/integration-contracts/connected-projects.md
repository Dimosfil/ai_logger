# Connected Projects

Last reviewed: 2026-09-29

This register records external local repositories that are intentionally used as
architecture or implementation sources for `ai_logger`. Do not treat sibling
folders as in scope unless they are listed here or the user explicitly names
them for the current task.

## LLM Providers

- Local path: `D:\AI\llm_providers`
- Repository: `https://github.com/Dimosfil/llm_providers.git`
- Role: reusable Node.js provider boundary for LLM and local agent runtimes.
- Current ai_logger use: logic source for the Python smart log-search provider
  registry, including the Codex app-server provider shape; no Node.js runtime
  dependency is wired.
- Source of truth: `D:\AI\llm_providers\README.md`,
  `D:\AI\llm_providers\tools\project-memory\specs\provider-architecture.md`,
  and package exports in `D:\AI\llm_providers\package.json`.
- Privacy boundary: inspect source, tests, README/docs, manifests, and compact
  project-memory specs only. Do not read secrets, local runtime config, logs,
  databases, generated artifacts, or unrelated sibling repositories.
- Update command: use that repository's own instructions before any write,
  dependency update, build, test, commit, or push.

## AI Media Client

- Local path: `D:\AI\ai-media-client`
- Repository: `https://github.com/sidindeep/ai-media-client`
- Role: planned first Node.js client of the cross-stack HTTP ingest protocol and
  reference for Docker Compose, private `.env`, and PostgreSQL operations.
- Current logging sources: `src/generation-log.js` writes a private rotating
  diagnostic JSONL journal; `src/system-errors.js` stores sanitized system
  errors in PostgreSQL `media_system_errors`; the account generation journal
  remains an application-owned PostgreSQL workflow.
- Prepared ai_logger edge: `clients/node/ai-logger-client.mjs` forwards selected sanitized
  system and lifecycle events to `/ingest` with a project-bound ingest key.
  The module remains in `ai_logger` for later transfer; no files in
  `ai-media-client` were changed. Existing local journals remain in place.
  Media prompts, tokens, cookies, and raw provider payloads stay out of
  central logs.
- Deployment evidence: `AGENTS.md`, `compose.yaml`, `Dockerfile`, `.env.example`,
  `README.md`, `docs/generation-logging.md`, and
  `docs/database-roles-and-migrations.md`. Runtime Compose reads a private `.env`
  and uses an external PostgreSQL connection; its `postgres-test` service is
  limited to the test profile.
- Ownership: AI Media Client owns generation events and account data; ai_logger
  owns its ingest protocol and future central storage. Do not share their
  database schemas or credentials.
- Privacy boundary: inspect instructions, source, tests, public docs, and
  example configuration only. Do not read `.env`, runtime logs, databases,
  generated media, or account data without an explicit task and scope.
- Change procedure: follow AI Media Client's `AGENTS.md` before writes. Its
  required post-edit verification is `docker compose up -d --build`, service
  status, and `http://127.0.0.1:3000/api/health`.
