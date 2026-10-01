# Portable Node.js client

Copy `ai-logger-client.mjs` into a Node.js 18+ backend project, or package this directory.
It has no external dependencies and sends the shared `/ingest` protocol.

```js
import { AiLoggerClient } from './ai-logger-client.mjs';

const logger = AiLoggerClient.fromEnv();
await logger.send({
  level: 'ERROR',
  logger: 'ai-media-client.system-errors',
  message: 'provider.request_failed',
  context: { component: 'generation', error_code: 'UPSTREAM_TIMEOUT', request_id: '...' },
});
```

Set `AI_LOGGER_SERVER_URL` to the public HTTPS `/ingest` URL and
`AI_LOGGER_PROJECT=ai-media-client`. No API key is needed. Optional values are
`AI_LOGGER_SERVICE`, `AI_LOGGER_ENVIRONMENT`, `AI_LOGGER_INSTANCE_ID`, and
`AI_LOGGER_FALLBACK_JSONL_PATH`. The client forwards only selected diagnostic
context fields; application code must pass sanitized event names and must not
pass prompts, cookies, credentials, or provider payloads in `message`.
`send()` returns `false` on delivery failure and writes a JSONL fallback when
configured. The application can keep its existing local journal while this
central route is introduced.
The client rejects unencrypted remote URLs. HTTP is allowed for localhost, or
for private LAN addresses when `AI_LOGGER_ALLOW_PRIVATE_HTTP=1` is explicitly
set. Public HTTP addresses remain rejected.

Set `AI_LOGGER_INSTANCE_ID=my-pc` in the sending application's private
environment; use a different stable value on another machine, such as
`friend-pc` or `bothost`. The client sends it as `context.instance_id`
on every record, independently of the process role in `service`.
Pass the same value into all Docker containers on that machine and retain it
across container recreation. No container hostname or generated run ID is used.
When unset, the field is omitted. Events cannot override a configured ID.

## Reusable system error recorder

The temporary `ai-media-client` system-error implementation has been extracted
into `system-errors.mjs`, `sanitize.mjs`, and `system-errors.sql`. Copy all three
files together. Each recorder has its own queue and sanitizer; it does not
import application code or depend on the source repository.

For private PostgreSQL diagnostics, supply a `pg`-compatible pool connected to
the **logger-owned database**. Apply the schema explicitly before recording:

```js
import {
  ensureSystemErrorSchema, createPostgresSystemErrorSink, createSystemErrorRecorder,
} from './system-errors.mjs';

// pool is supplied by your runtime; this module does not create connections.
await ensureSystemErrorSchema(pool);
const project = process.env.AI_LOGGER_PROJECT;
const errors = createSystemErrorRecorder({
  sink: createPostgresSystemErrorSink(pool, project),
});
errors.startRetention(pool, project); // run in one designated maintenance process
const restoreConsole = errors.captureConsole(); // optional
errors.secret(process.env.PROVIDER_API_KEY);
errors.record('worker', 'provider.failed', new Error('upstream unavailable'), { status: 503 });

// During shutdown: stop producers first, then attempt a final drain.
restoreConsole();
await errors.flush();
const remaining = await errors.close();
// remaining.pending reports rows that could not be delivered; the queue is in memory.
```

The separate `ai_logger_system_errors` table stores `project`, timestamp,
source, event, code, sanitized message, and sanitized details. Queries and
retention must specify the project. The default policy retains 90 days, deletes
at most 500 rows per pass, waits one hour between normal passes, one second
between full batches, and five minutes after failures. `startRetention()`
accepts overrides for these settings and starts after 30 seconds.

The queue holds at most 500 rows and retries failed delivery after five seconds.
Both bounds are constructor options. Overflow removes the oldest waiting row;
an in-flight row stays protected. `status()` reports pending/dropped counts.
`record()` returns false if recording fails or the recorder has closed.
`setSink()` attaches or replaces a sink and starts draining queued rows.
Sink functions reject or return false on failure. Do not share mutable sinks
or retain raw application payloads in custom sinks.

The sanitizer removes registered secrets, credential fields, bearer tokens,
URL credentials/query/fragment, and binary content. It bounds depth, collection
size, strings, and error messages. Register secrets before logging them;
sanitization does not turn arbitrary business data into public data.

For the existing open HTTP ingest service, use
`createHttpSystemErrorSink(AiLoggerClient.fromEnv())` instead of the PostgreSQL
sink. It forwards event/source/error-code metadata plus sanitized Error type,
message and stack (100/1000/4000 characters). Arbitrary private details and
plain-string private messages stay local. Supply selected description, file,
line, function and entity in `details.diagnostic` when recording:

```js
errors.record('startup', 'startup.error', new Error('Missing port setting'), {
  diagnostic: { description: 'Missing port setting', file: 'src/config.js',
    line: 12, function: 'loadConfig', entity: 'executor' },
});
```

Error messages must contain diagnostic information; keep prompts, business
data and provider payloads out of them. Register known secrets before capture.
The HTTP sink uses the existing `ai_logger_records` storage; the private error
table is a separate opt-in store, not a new public HTTP endpoint.

Extraction does not change `ai-media-client`, apply schema to a live database,
copy historical rows, or retire `media_system_errors`. Its existing module,
table, and readers continue operating until a separate switch is requested.

Verify the portable modules from this repository's root:

```powershell
node --test clients/node/ai-logger-client.test.mjs clients/node/system-errors.test.mjs
```
