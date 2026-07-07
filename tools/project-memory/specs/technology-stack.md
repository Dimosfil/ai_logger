# Technology Stack

Last reviewed: 2026-07-06

Canonical source: this file
Linked from: TODO

This is project documentation. Keep business rules, feature algorithms, workflow
contracts, state machines, and verification guarantees in project memory; keep
stack facts, commands, runtime assumptions, and operational notes here.

## Summary

- Primary stack: Python package
- Runtime model: protocol-first client adapters plus optional local ingest server
- Current confidence: verified from `pyproject.toml`, `src/ai_logger/`, and tests

## Components

| Layer | Technology | Evidence | Notes |
| --- | --- | --- | --- |
| Language/runtime | Python >= 3.9 | `pyproject.toml` | Standard-library implementation |
| Frontend | None | repository files | This is a library package |
| Backend/API | HTTP ingest protocol, Python reference SDK, and stdlib HTTP ingest server | `docs/ingest-protocol.md`, `src/ai_logger/`, `src/ai_logger/server.py` | Cross-stack adapters send normalized records to `/ingest` |
| Data/storage | JSON Lines log files through plugin | `src/ai_logger/plugins.py` | Storage is plugin-configured, not a required app database |
| AI analysis | Optional LLM-backed log search | `src/ai_logger/llm.py`, `src/ai_logger/log_search.py` | DeepSeek is the first provider; provider is swappable |
| Build/package | setuptools | `pyproject.toml` | Editable install supported |
| Test/quality | unittest | `tests/test_logging_core.py`, `tests/test_client_server.py` | Run with standard Python test discovery |
| Deployment/runtime | Native client adapters plus local server command | `README.md`, `docs/client-adapters.md`, `pyproject.toml` | Project agents configure the adapter matching each stack |

## Commands

| Purpose | Command | Evidence |
| --- | --- | --- |
| Install | `python -m pip install -e .` | `README.md`, `pyproject.toml` |
| Run | Import `ai_logger` from a host application; run server with `python -m ai_logger.server` or `ai-logger-server` | `README.md`, `pyproject.toml` |
| Search logs | `ai-logger-log-search "problem description"` | `pyproject.toml`, `docs/llm-log-search.md` |
| Test | `python -m unittest discover -s tests` | `README.md`, `tests/test_logging_core.py`, `tests/test_client_server.py` |
| Build | `python -m build` when build tooling is installed | `pyproject.toml` |

## External Services

| Service | Role | Evidence | Boundary |
| --- | --- | --- | --- |
| ai_logger ingest server | Receives project client logs at `/ingest` | `src/ai_logger/server.py` | Optional bearer token |
| Graylog GELF HTTP input | Optional server backend | `src/ai_logger/plugins.py` | Configured by `AI_LOGGER_GRAYLOG_GELF_URL` |
| ClickHouse HTTP endpoint | Optional server backend | `src/ai_logger/plugins.py` | Configured by `AI_LOGGER_CLICKHOUSE_URL` and `AI_LOGGER_CLICKHOUSE_TABLE` |
| DeepSeek API | Optional LLM provider for smart log search | `src/ai_logger/llm.py`, `docs/llm-log-search.md` | Key read from `DEEPSEEK_API_KEY` or `AI_LOGGER_DEEPSEEK_API_KEY`; never persisted |

## Gaps

- AI bot analysis is currently a CLI/read-side JSONL search flow; no long-lived
  analysis server or chat UI is implemented yet.
- No release publishing workflow is documented yet.
