# ai_logger Ingest Protocol

`ai_logger` is protocol-first. Client adapters may be implemented for any stack:
Python logging, NLog, log4net, Serilog, pino, winston, Java logging, Go slog, or
custom project code.

Every adapter sends normalized JSON records to the ai_logger server:

```text
POST /ingest
Authorization: Bearer <optional-token>
Content-Type: application/json; charset=utf-8
```

The request body may be one record object or an array of record objects.

## Record Shape

```json
{
  "id": "record-id",
  "timestamp": "2026-07-06T12:30:00+00:00",
  "logger": "project.service.component",
  "level": "ERROR",
  "level_value": 40,
  "message": "job.failed",
  "context": {
    "project": "billing",
    "service": "worker",
    "environment": "prod",
    "trace_id": "trace-1",
    "request_id": "req-1"
  },
  "tags": ["job"],
  "exception": {
    "type": "ValueError",
    "message": "bad input",
    "stack_trace": "..."
  }
}
```

Required fields:

- `timestamp`
- `logger`
- `level` or `level_value`
- `message`

Recommended context fields:

- `project`
- `service`
- `environment`
- `host`
- `trace_id`
- `span_id`
- `request_id`
- `user_id`, only when allowed by project privacy policy

## Adapter Duties

Each client adapter should:

- map the native logging level to `level` and `level_value`;
- preserve logger/category name;
- attach project, service, environment, host, and trace/request identifiers;
- serialize exception type, message, and stack trace when available;
- send records to `/ingest`;
- buffer or fallback locally when the server is unavailable;
- avoid sending secrets, tokens, passwords, cookies, private keys, or raw
  sensitive payloads.

The ai_logger server does not depend on the client stack. It receives normalized
records and routes them to backend plugins such as JSONL, Graylog GELF,
ClickHouse, or future sinks.
