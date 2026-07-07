# LLM Log Search

`ai_logger` can search local JSON Lines logs with a two-step flow:

1. local ranking finds a small candidate set from recent records;
2. an optional LLM provider ranks those candidates and writes a short incident
   summary.

The first provider is DeepSeek. The provider is optional at runtime; local
ranking still works without an API key.

## Command

```powershell
$env:AI_LOGGER_SERVER_JSONL_PATH = "logs/server.jsonl"
$env:DEEPSEEK_API_KEY = "<secret>"
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

## Configuration

- `AI_LOGGER_LOG_SEARCH_JSONL_PATH`: explicit search source.
- `AI_LOGGER_SERVER_JSONL_PATH`: server JSONL sink path used when the explicit
  search path is not set.
- `AI_LOGGER_JSONL_PATH`: client JSONL sink path used as a final fallback.
- `AI_LOGGER_LOG_SEARCH_MAX_RECORDS`: recent records to scan, default `500`.
- `AI_LOGGER_LOG_SEARCH_CANDIDATES`: local candidates sent to the LLM, default
  `30`.
- `AI_LOGGER_LOG_SEARCH_TOP_K`: returned matches, default `5`.
- `AI_LOGGER_LLM_PROVIDER`: `deepseek`, `local`, or `none`; default `deepseek`.
- `DEEPSEEK_API_KEY` or `AI_LOGGER_DEEPSEEK_API_KEY`: DeepSeek bearer token.
- `AI_LOGGER_DEEPSEEK_BASE_URL`: default `https://api.deepseek.com`.
- `AI_LOGGER_DEEPSEEK_MODEL`: default `deepseek-v4-flash`.
- `AI_LOGGER_DEEPSEEK_TIMEOUT`: request timeout seconds, default `30`.
- `AI_LOGGER_DEEPSEEK_MAX_TOKENS`: response token cap, default `1200`.
- `AI_LOGGER_DEEPSEEK_THINKING`: enables DeepSeek thinking mode when set to
  `1`, `true`, `yes`, `on`, or `enabled`.

## Privacy And Secrets

The search path never stores provider keys in logs, code, docs, or project
memory. DeepSeek receives only the local shortlist, not the full log file.
Known secret fields such as `token`, `password`, `authorization`, `cookie`,
`secret`, and `api_key` are redacted before candidates are sent to the LLM.

## Provider Boundary

`SmartLogSearcher` depends on the `LogSearchLlmProvider` protocol. New providers
should implement the same `analyze(query, candidates, top_k=...)` shape and keep
provider credentials in environment variables or a managed secret store.
