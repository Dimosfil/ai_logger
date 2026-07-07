from __future__ import annotations

import os
from typing import Mapping

from .llm import (
    CodexAppServerChatClient,
    DeepSeekChatClient,
    LlmProviderError,
    MockChatClient,
    OpenAiCompatibleChatClient,
)
from .log_search import LogSearchLlmProvider, StructuredLlmLogSearchProvider


LOCAL_PROVIDER_NAMES = {"local", "none", "off", "disabled", "no-llm"}


def normalize_log_search_provider(value: str | None) -> str:
    provider = (value or "").strip().lower()
    if provider in LOCAL_PROVIDER_NAMES:
        return "local"
    if provider in {"mock", "test"}:
        return "mock"
    if provider in {"openai-compatible", "openai", "compatible"}:
        return "openai-compatible"
    if provider in {"codex", "codex-app-server", "app-server"}:
        return "codex"
    if provider == "deepseek":
        return "deepseek"
    if provider == "":
        return "codex"
    return "codex"


def create_log_search_llm_provider(
    provider_name: str | None = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> LogSearchLlmProvider | None:
    env = environ or os.environ
    provider = normalize_log_search_provider(
        provider_name or env.get("AI_LOGGER_LLM_PROVIDER") or env.get("LLM_PROVIDER")
    )
    if provider == "local":
        return None
    if provider == "mock":
        return StructuredLlmLogSearchProvider("mock", MockChatClient.from_env(env))
    if provider == "openai-compatible":
        return StructuredLlmLogSearchProvider(
            "openai-compatible",
            OpenAiCompatibleChatClient.from_env(env),
        )
    if provider == "codex":
        return StructuredLlmLogSearchProvider("codex", CodexAppServerChatClient.from_env(env))
    if provider == "deepseek":
        return StructuredLlmLogSearchProvider("deepseek", DeepSeekChatClient.from_env(env))
    raise LlmProviderError(f"Unsupported LLM provider: {provider_name}")
