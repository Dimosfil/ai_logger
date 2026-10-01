# Reusable system error recorder

Last verified: 2026-09-30. Status: extracted, opt-in module; source application unchanged.

## Ownership and source mapping

`ai_logger` owns the reusable recorder, sanitizer and private error schema.
The source is `D:\AI\ai-media-client\src\system-errors.js`, its schema
`src/database/migrations/0014-system-errors.sql`, and the `clean`/`secret`
functions in `src/generation-log.js`. This adoption covers system errors;
generation JSONL rotation and HTTP tracing remain application-owned.

Current implementation: `clients/node/system-errors.mjs`, `sanitize.mjs`,
`system-errors.sql`. Evidence: `clients/node/system-errors.test.mjs` and
`ai-logger-client.test.mjs`. Operation guide: `clients/node/README.md`.
Verification on 2026-09-30: 12 Node tests passed. An isolated PostgreSQL 17
container executed the shipped schema twice, the sink's generated insert and
retention queries; sanitized persistence, batch limits and preservation of
another project's rows passed. The verification container was removed. Live
consumer integration and existing-database migration were not part of extraction.

## Portable behavior contract

An instance accepts source, event, error, and details. It sanitizes before
enqueueing: credential keys, registered secrets, bearer/Telegram tokens,
URL credentials/query/fragment and binary content are removed. Recursion is
bounded at depth 12, collections at 100 entries, strings at 32768 characters;
source/event/code/message are limited to 100/150/100/4000 characters.
Error causes are also bounded. Secret sets and queues are instance-local.
Application errors and recursive sanitization failures do not propagate from
the recording operation. Normal console output is preserved when intercepted;
the interception can be restored independently of recorder shutdown.

Records wait in a bounded memory queue (default 500). Overflow drops the
oldest waiting record, protects the in-flight record, and increments a counter.
Delivery is serialized. A failed sink call or false result retains the record
and schedules an unref'ed retry (default 5 seconds). No sink means records wait
until one is attached. A successful sink call removes exactly that record.
Crash/restart can lose queued records; delivery is at least once after ambiguous
sink failures and this private schema has no retry deduplication guarantee.

The PostgreSQL sink receives an externally managed, pg-compatible pool.
Schema creation is explicit, idempotent, and separate from construction.
`ai_logger_system_errors` owns identity ID, project, occurrence time, source,
event, optional code, message and JSON details. The timestamp is database
insertion time, matching the source table. SQL values are parameterized; table
identifiers are fixed. No application-owned table or credential is reused.

Retention deletes only the selected project's expired rows in bounded oldest
first batches (defaults 90 days / 500 rows). One designated maintenance process
starts after 30 seconds and checks hourly, continues full batches after one
second, and retries database errors after five minutes. Policy is configurable.
Stop/restart prevents stale callbacks from scheduling more work. Close stops
retry/retention, waits for work already in progress, and reports pending/dropped
rows; callers stop producers and explicitly flush before close.

The HTTP sink is a separate privacy boundary. It emits ERROR records through
the existing portable client and `/ingest` protocol, with identifier-shaped
event/source/code. As of 2026-09-30 it also forwards sanitized Error
type/message/stack and explicitly selected `details.diagnostic` fields:
description/file/line/function/entity. Error stack and registered secrets pass
through the recorder sanitizer before delivery; the HTTP client bounds
exception type/message/stack to 100/1000/4000 characters. Applications own
diagnostic message content and must keep business/provider payloads out.
Arbitrary private message/details and plain-string errors remain local. It does not
write the new private table or expose a public reader for it.

## Rollout boundary

The user selected extraction while retaining the working source code. No
`ai-media-client` file or live database is modified. Its `media_system_errors`
schema, runtime behavior and readers remain current. No historical data
migration is performed. Any later consumer switch must preserve its internal
recording API, read paths and database privacy; introducing a private central
HTTP storage/read endpoint requires its own contract.
