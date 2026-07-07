# LLM Providers Logic Map

Last reviewed: 2026-07-07

Source: `D:\AI\llm_providers`

## Purpose

`llm_providers` is a reusable Node.js ESM package that isolates LLM transport
and local agent runtime calls behind one provider contract. For `ai_logger`, it
is a portable logic source for making smart log search providers swappable
without binding search behavior to DeepSeek-specific code.

## Source Evidence

- Package/public API: `D:\AI\llm_providers\package.json`,
  `D:\AI\llm_providers\src\index.mjs`
- Architecture spec:
  `D:\AI\llm_providers\tools\project-memory\specs\provider-architecture.md`
- Provider registry/config:
  `D:\AI\llm_providers\src\providerRegistry.mjs`,
  `D:\AI\llm_providers\src\config.mjs`
- Provider adapters:
  `D:\AI\llm_providers\src\providers\openai-compatible\index.mjs`,
  `D:\AI\llm_providers\src\providers\deepseek\index.mjs`,
  `D:\AI\llm_providers\src\providers\mock\index.mjs`,
  `D:\AI\llm_providers\src\providers\codex-app-server\index.mjs`
- Output contracts:
  `D:\AI\llm_providers\src\outputContracts.mjs`
- Verification:
  `D:\AI\llm_providers\test\providers.test.mjs`,
  `D:\AI\llm_providers\test\outputContracts.test.mjs`,
  `D:\AI\llm_providers\test\smoke.mjs`

## Portable Contracts

- Provider names are normalized to `mock`, `deepseek`, `openai-compatible`, or
  `codex`; unknown provider input defaults to DeepSeek.
- Provider config is assembled from environment values plus caller overrides.
  Secrets stay in environment or caller-owned runtime config.
- The provider registry creates the active provider and exposes
  `generateWithActiveProvider(config, request, callbacks)`.
- Provider requests can use either a plain `prompt` or chat-style `messages`,
  plus model, temperature, max token, metadata, and output parsing options.
- Provider results include provider name, model, raw text output, optional
  parsed output, and provider raw response when available.
- OpenAI-compatible providers own `/chat/completions` transport and only add
  `response_format: {"type":"json_object"}` when whole-output JSON parsing is
  requested without a fenced block marker.
- DeepSeek is a preset over the OpenAI-compatible provider.
- Mock provider is always configured and returns deterministic output for tests
  and offline development.
- Codex app-server provider starts an ephemeral local Codex thread with
  developer instructions that forbid file edits, file inspection, shell
  commands, and approval requests.
- Output contracts extract marked fenced JSON blocks, parse JSON, and then run
  caller-owned validation.

## Mapping To ai_logger

Current `ai_logger` smart search has a narrower Python protocol:
`LogSearchLlmProvider.analyze(query, candidates, top_k=...)` in
`src/ai_logger/log_search.py`. Provider selection is implemented in
`src/ai_logger/log_search_providers.py`, and stdlib transport/runtime clients
live in `src/ai_logger/llm.py`.

The integration is a logic adoption, not a Node.js runtime dependency.
`ai_logger` keeps its dependency-free Python package boundary and mirrors the
portable provider concepts in Python so the web UI and CLI can search logs
without requiring Node.js or importing `llm_providers` at runtime.

Current implementation evidence in `ai_logger`:

- Provider registry: `src/ai_logger/log_search_providers.py`
- Codex app-server, OpenAI-compatible, DeepSeek, and mock clients:
  `src/ai_logger/llm.py`
- Log-search domain protocol and candidate shaping:
  `src/ai_logger/log_search.py`
- CLI provider selection: `src/ai_logger/log_search_cli.py`
- Web UI provider selector and `/api/search` routing:
  `src/ai_logger/web.py`, `src/ai_logger/server.py`
- Verification: `tests/test_log_search.py`, `tests/test_client_server.py`

Portable logic adopted:

- Split provider transport/config from log-search ranking and prompt shaping.
- Add a small provider registry so `AI_LOGGER_LLM_PROVIDER` can select Codex
  app-server, DeepSeek, local-only, mock/test, and OpenAI-compatible providers
  consistently.
- Keep the log-search domain contract as the caller-owned layer: it should build
  candidate payloads, redact values, validate returned record IDs, and preserve
  local fallback behavior.
- Keep mock provider behavior deterministic for tests and offline verification.
- Keep provider choice request-scoped in the web UI when the user selects a
  specific provider, while preserving automatic environment-driven routing.
- Adopt Codex app-server as the default provider with model
  `gpt-codex-spark-high`; keep the app-server thread ephemeral and constrained
  by developer instructions that forbid file edits, file inspection, shell
  commands, and approval requests.

Portable logic still deferred:

- Full output-contract parity with `outputContracts.mjs`; the current Python
  providers request whole-response JSON objects and only tolerate simple fenced
  JSON around Codex output.
- Generic `ProviderResult` fields such as raw text output, parsed output, and
  raw provider response are intentionally collapsed into `LlmLogSearchAnalysis`
  for log search. Preserve that narrower domain result unless another feature
  needs generic provider responses.

Environment mapping:

- Default provider is `codex`. `AI_LOGGER_CODEX_MODEL` / `CODEX_MODEL`
  default to `gpt-codex-spark-high`; `AI_LOGGER_CODEX_COMMAND` /
  `CODEX_COMMAND` can override the app-server command path.
- `llm_providers` generic variables (`LLM_PROVIDER`, `LLM_BASE_URL`,
  `LLM_API_KEY`, `LLM_MODEL`, `LLM_MOCK_RESPONSE`) are accepted by
  `ai_logger`.
- `ai_logger` also exposes namespaced aliases (`AI_LOGGER_LLM_PROVIDER`,
  `AI_LOGGER_LLM_BASE_URL`, `AI_LOGGER_LLM_API_KEY`,
  `AI_LOGGER_LLM_MODEL`, `AI_LOGGER_LLM_MOCK_RESPONSE`) so host projects can
  configure log search without colliding with another app-level LLM provider.
- DeepSeek keeps both shared and historical variables:
  `DEEPSEEK_API_KEY`, `DEEPSEEK_BASE_URL`, `DEEPSEEK_MODEL`,
  plus `AI_LOGGER_DEEPSEEK_API_KEY`, `AI_LOGGER_DEEPSEEK_BASE_URL`, and
  `AI_LOGGER_DEEPSEEK_MODEL`.

## Non-Goals

- Do not copy the Node.js source into `ai_logger`.
- Do not add API keys, generated outputs, provider logs, local Codex runtime
  state, or machine-specific config to project memory.
- Do not change the ingest protocol or backend plugin model as part of provider
  adoption.

## Verification Gaps

- Real provider integration tests should remain opt-in and environment-gated.
