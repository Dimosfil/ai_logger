# LLM Log Search

`ai_logger` can search local JSON Lines logs with a two-step flow:

1. local ranking finds a small candidate set from recent records;
2. an optional LLM provider ranks those candidates and writes a short incident
   summary.

The provider is optional at runtime; local ranking still works without an API
key. The default provider is local Codex app-server with model
`gpt-codex-spark-high`. The provider boundary follows the reusable
`llm_providers` contract: `codex`, `deepseek`, `openai-compatible`, and `mock`
are provider-backed modes, while `local` and `none` skip the LLM call.

## Command

```powershell
$env:AI_LOGGER_SERVER_JSONL_PATH = "logs/server.jsonl"
$env:AI_LOGGER_LLM_PROVIDER = "codex"
$env:AI_LOGGER_CODEX_MODEL = "gpt-codex-spark-high"
ai-logger-log-search "authorization fails after deploy"
```

Use the shared provider contract with any OpenAI-compatible chat-completions
endpoint:

```powershell
$env:AI_LOGGER_LLM_PROVIDER = "openai-compatible"
$env:AI_LOGGER_LLM_BASE_URL = "https://llm.example.test/v1"
$env:AI_LOGGER_LLM_API_KEY = "<secret>"
$env:AI_LOGGER_LLM_MODEL = "your-model"
ai-logger-log-search "authorization fails after deploy"
```

Local-only mode does not call an external service:

```powershell
ai-logger-log-search "authorization fails after deploy" --no-llm
```

JSON output is useful for tools:

```powershell
ai-logger-log-search "worker timeout" --format json
```

The local web UI at `http://127.0.0.1:8765/` uses the same provider registry in
its natural-language search box. Leave the provider selector on `Auto provider`
to use `AI_LOGGER_LLM_PROVIDER` / `LLM_PROVIDER`, or choose a provider for that
single request.

## Configuration

- `AI_LOGGER_LOG_SEARCH_JSONL_PATH`: explicit search source.
- `AI_LOGGER_SERVER_JSONL_PATH`: server JSONL sink path used when the explicit
  search path is not set.
- `AI_LOGGER_JSONL_PATH`: client JSONL sink path used as a final fallback.
- `AI_LOGGER_LOG_SEARCH_MAX_RECORDS`: recent records to scan, default `500`.
- `AI_LOGGER_LOG_SEARCH_CANDIDATES`: local candidates sent to the LLM, default
  `30`.
- `AI_LOGGER_LOG_SEARCH_TOP_K`: returned matches, default `5`.
- `AI_LOGGER_LLM_PROVIDER` or `LLM_PROVIDER`: `codex`, `deepseek`,
  `openai-compatible`, `mock`, `local`, or `none`; default `codex`.
- `AI_LOGGER_CODEX_COMMAND` or `CODEX_COMMAND`: Codex command path; on Windows
  defaults to `%USERPROFILE%\.codex\bin\codex.cmd` when present.
- `AI_LOGGER_CODEX_MODEL` or `CODEX_MODEL`: Codex app-server model, default
  `gpt-codex-spark-high`.
- `AI_LOGGER_CODEX_EFFORT` or `CODEX_EFFORT`: `low`, `medium`, or `high`;
  default `high`.
- `AI_LOGGER_CODEX_REQUEST_TIMEOUT_SECONDS` or
  `CODEX_REQUEST_TIMEOUT_SECONDS`: JSON-RPC request timeout, default `30`.
- `AI_LOGGER_CODEX_TURN_TIMEOUT_SECONDS` or `CODEX_TURN_TIMEOUT_SECONDS`:
  turn completion timeout, default `180`.
- `DEEPSEEK_API_KEY` or `AI_LOGGER_DEEPSEEK_API_KEY`: DeepSeek bearer token.
- `AI_LOGGER_DEEPSEEK_BASE_URL` or `DEEPSEEK_BASE_URL`: default
  `https://api.deepseek.com`.
- `AI_LOGGER_DEEPSEEK_MODEL` or `DEEPSEEK_MODEL`: default
  `deepseek-v4-flash`.
- `AI_LOGGER_DEEPSEEK_TIMEOUT`: request timeout seconds, default `30`.
- `AI_LOGGER_DEEPSEEK_MAX_TOKENS`: response token cap, default `1200`.
- `AI_LOGGER_DEEPSEEK_THINKING`: enables DeepSeek thinking mode when set to
  `1`, `true`, `yes`, `on`, or `enabled`.
- `AI_LOGGER_LLM_BASE_URL` or `LLM_BASE_URL`: base URL for
  `openai-compatible`.
- `AI_LOGGER_LLM_API_KEY` or `LLM_API_KEY`: bearer token for
  `openai-compatible`.
- `AI_LOGGER_LLM_MODEL` or `LLM_MODEL`: model for `openai-compatible`.
- `AI_LOGGER_LLM_TIMEOUT`: generic provider request timeout seconds, default
  `30`.
- `AI_LOGGER_LLM_MAX_TOKENS`: generic provider response token cap, default
  `1200`.
- `AI_LOGGER_LLM_MOCK_RESPONSE` or `LLM_MOCK_RESPONSE`: deterministic JSON
  response for `mock`.

## Privacy And Secrets

The search path never stores provider keys in logs, code, docs, or project
memory. The active provider receives only the local shortlist, not the full log
file.
Known secret fields such as `token`, `password`, `authorization`, `cookie`,
`secret`, and `api_key` are redacted before candidates are sent to the LLM.

## Provider Boundary

`SmartLogSearcher` depends on the `LogSearchLlmProvider` protocol. New providers
should implement the same `analyze(query, candidates, top_k=...)` shape and keep
provider credentials in environment variables or a managed secret store.

## Best Practices For LLM-Assisted Log Search

- Keep deterministic retrieval first: filter and rank recent records locally,
  then send only a bounded candidate set to the LLM.
- Keep provider transport separate from log-search behavior. The search layer
  owns prompts, redaction, record-id validation, local fallback, and output
  shape.
- Treat log content as untrusted input. Prompts should tell the model to choose
  from supplied record IDs only and never follow instructions found inside log
  messages or stack traces.
- Redact secrets before provider calls and keep API keys in environment
  variables or managed secrets.
- Prefer structured log fields and stable vocabulary so local ranking, future
  vector search, dashboards, and incident workflows can reuse the same data.
- Use `mock` and `--no-llm` in tests and CI. Real provider tests should be
  opt-in and environment-gated.
- Return evidence with every answer: provider name, summary, selected records,
  scores, reasons, warnings, and original record IDs.
