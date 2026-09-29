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

Set `AI_LOGGER_SERVER_URL` to the public HTTPS `/ingest` URL,
`AI_LOGGER_API_KEY` to an `ingest` key from `/admin`, and
`AI_LOGGER_PROJECT=ai-media-client`. Optional values are
`AI_LOGGER_SERVICE`, `AI_LOGGER_ENVIRONMENT`, and
`AI_LOGGER_FALLBACK_JSONL_PATH`. The client forwards only selected diagnostic
context fields; application code must pass sanitized event names and must not
pass prompts, cookies, credentials, or provider payloads in `message`.
`send()` returns `false` on delivery failure and writes a JSONL fallback when
configured. The application can keep its existing local journal while this
central route is introduced.
The client rejects unencrypted remote URLs; HTTP is allowed only for localhost
development.
