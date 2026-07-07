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
`src/ai_logger/log_search_providers.py`, and stdlib transport clients live in
`src/ai_logger/llm.py`.

Portable logic adopted:

- Split provider transport/config from log-search ranking and prompt shaping.
- Add a small provider registry so `AI_LOGGER_LLM_PROVIDER` can select DeepSeek,
  local-only, mock/test, and OpenAI-compatible providers consistently.
- Keep the log-search domain contract as the caller-owned layer: it should build
  candidate payloads, redact values, validate returned record IDs, and preserve
  local fallback behavior.
- Keep mock provider behavior deterministic for tests and offline verification.

Portable logic still deferred:

- Fenced JSON block extraction equivalent to `outputContracts.mjs`; the current
  Python providers request whole-response JSON objects.
- Codex app-server provider integration.

## Non-Goals

- Do not copy the Node.js source into `ai_logger`.
- Do not add API keys, generated outputs, provider logs, local Codex runtime
  state, or machine-specific config to project memory.
- Do not change the ingest protocol or backend plugin model as part of provider
  adoption.

## Verification Gaps

- Real provider integration tests should remain opt-in and environment-gated.
