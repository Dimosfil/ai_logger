from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping
from urllib import request


class LlmProviderError(RuntimeError):
    """Raised when an LLM provider cannot complete a log search request."""


@dataclass(frozen=True)
class DeepSeekOptions:
    api_key: str
    model: str = "deepseek-v4-flash"
    base_url: str = "https://api.deepseek.com"
    timeout_seconds: float = 30.0
    max_tokens: int = 1200
    thinking_enabled: bool = False

    @property
    def chat_completions_url(self) -> str:
        normalized = self.base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"


@dataclass(frozen=True)
class OpenAiCompatibleOptions:
    api_key: str
    base_url: str
    model: str = "gpt-4.1-mini"
    timeout_seconds: float = 30.0
    max_tokens: int = 1200

    @property
    def chat_completions_url(self) -> str:
        normalized = self.base_url.rstrip("/")
        if normalized.endswith("/chat/completions"):
            return normalized
        return f"{normalized}/chat/completions"


class OpenAiCompatibleChatClient:
    """Small stdlib OpenAI-compatible chat-completions client for JSON responses."""

    def __init__(self, options: OpenAiCompatibleOptions) -> None:
        self.options = options

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "OpenAiCompatibleChatClient":
        env = environ or os.environ
        api_key = env.get("AI_LOGGER_LLM_API_KEY") or env.get("LLM_API_KEY")
        base_url = env.get("AI_LOGGER_LLM_BASE_URL") or env.get("LLM_BASE_URL")
        if not base_url:
            raise LlmProviderError("AI_LOGGER_LLM_BASE_URL or LLM_BASE_URL is required.")
        if not api_key:
            raise LlmProviderError("AI_LOGGER_LLM_API_KEY or LLM_API_KEY is required.")
        return cls(
            OpenAiCompatibleOptions(
                api_key=api_key,
                base_url=base_url,
                model=env.get("AI_LOGGER_LLM_MODEL") or env.get("LLM_MODEL") or "gpt-4.1-mini",
                timeout_seconds=float(env.get("AI_LOGGER_LLM_TIMEOUT", "30")),
                max_tokens=int(env.get("AI_LOGGER_LLM_MAX_TOKENS", "1200")),
            )
        )

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return post_chat_completion_json(
            url=self.options.chat_completions_url,
            api_key=self.options.api_key,
            model=self.options.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=self.options.timeout_seconds,
            max_tokens=self.options.max_tokens,
            provider_name="OpenAI-compatible provider",
        )


class DeepSeekChatClient:
    """Small stdlib DeepSeek chat-completions client for JSON responses."""

    def __init__(self, options: DeepSeekOptions) -> None:
        self.options = options

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "DeepSeekChatClient":
        env = environ or os.environ
        api_key = env.get("DEEPSEEK_API_KEY") or env.get("AI_LOGGER_DEEPSEEK_API_KEY")
        if not api_key:
            raise LlmProviderError("DEEPSEEK_API_KEY or AI_LOGGER_DEEPSEEK_API_KEY is required.")
        return cls(
            DeepSeekOptions(
                api_key=api_key,
                model=env.get("AI_LOGGER_DEEPSEEK_MODEL")
                or env.get("DEEPSEEK_MODEL")
                or "deepseek-v4-flash",
                base_url=env.get("AI_LOGGER_DEEPSEEK_BASE_URL")
                or env.get("DEEPSEEK_BASE_URL")
                or "https://api.deepseek.com",
                timeout_seconds=float(env.get("AI_LOGGER_DEEPSEEK_TIMEOUT", "30")),
                max_tokens=int(env.get("AI_LOGGER_DEEPSEEK_MAX_TOKENS", "1200")),
                thinking_enabled=env.get("AI_LOGGER_DEEPSEEK_THINKING", "").lower()
                in {"1", "true", "yes", "on", "enabled"},
            )
        )

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        return post_chat_completion_json(
            url=self.options.chat_completions_url,
            api_key=self.options.api_key,
            model=self.options.model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout_seconds=self.options.timeout_seconds,
            max_tokens=self.options.max_tokens,
            provider_name="DeepSeek",
            extra_payload={
                "thinking": {"type": "enabled" if self.options.thinking_enabled else "disabled"}
            },
        )


class MockChatClient:
    """Deterministic JSON client for offline log-search tests and demos."""

    def __init__(self, response: Mapping[str, Any] | str | None = None) -> None:
        self.response = response or {
            "summary": "Mock provider returned the local candidates unchanged.",
            "matches": [],
        }

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "MockChatClient":
        env = environ or os.environ
        response = env.get("AI_LOGGER_LLM_MOCK_RESPONSE") or env.get("LLM_MOCK_RESPONSE")
        return cls(response)

    def complete_json(self, _system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if isinstance(self.response, Mapping):
            return dict(self.response)
        try:
            result = json.loads(self.response)
        except json.JSONDecodeError as exc:
            raise LlmProviderError("Mock provider response was not valid JSON.") from exc
        if not isinstance(result, dict):
            raise LlmProviderError("Mock provider JSON response must be an object.")
        if "matches" not in result:
            payload = json.loads(user_prompt)
            candidate_logs = payload.get("candidate_logs") or []
            if candidate_logs:
                result["matches"] = [{"id": candidate_logs[0].get("id", ""), "reason": "mock"}]
        return result


def post_chat_completion_json(
    *,
    url: str,
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    timeout_seconds: float,
    max_tokens: int,
    provider_name: str,
    extra_payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "stream": False,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    if extra_payload:
        payload.update(extra_payload)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    http_request = request.Request(
        url,
        data=data,
        headers=headers,
        method="POST",
    )
    try:
        with request.urlopen(http_request, timeout=timeout_seconds) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # pragma: no cover - exact urllib failures vary by platform.
        raise LlmProviderError(f"{provider_name} request failed: {exc}") from exc

    try:
        content = response_payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmProviderError(f"{provider_name} response did not contain message content.") from exc

    try:
        result = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LlmProviderError(f"{provider_name} response content was not valid JSON.") from exc
    if not isinstance(result, dict):
        raise LlmProviderError(f"{provider_name} JSON response must be an object.")
    return result
