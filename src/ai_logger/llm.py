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
                model=env.get("AI_LOGGER_DEEPSEEK_MODEL", "deepseek-v4-flash"),
                base_url=env.get("AI_LOGGER_DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
                timeout_seconds=float(env.get("AI_LOGGER_DEEPSEEK_TIMEOUT", "30")),
                max_tokens=int(env.get("AI_LOGGER_DEEPSEEK_MAX_TOKENS", "1200")),
                thinking_enabled=env.get("AI_LOGGER_DEEPSEEK_THINKING", "").lower()
                in {"1", "true", "yes", "on", "enabled"},
            )
        )

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        payload = {
            "model": self.options.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "max_tokens": self.options.max_tokens,
            "response_format": {"type": "json_object"},
            "thinking": {"type": "enabled" if self.options.thinking_enabled else "disabled"},
        }
        headers = {
            "Authorization": f"Bearer {self.options.api_key}",
            "Content-Type": "application/json; charset=utf-8",
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        http_request = request.Request(
            self.options.chat_completions_url,
            data=data,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(http_request, timeout=self.options.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover - exact urllib failures vary by platform.
            raise LlmProviderError(f"DeepSeek request failed: {exc}") from exc

        try:
            content = response_payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LlmProviderError("DeepSeek response did not contain message content.") from exc

        try:
            result = json.loads(content)
        except json.JSONDecodeError as exc:
            raise LlmProviderError("DeepSeek response content was not valid JSON.") from exc
        if not isinstance(result, dict):
            raise LlmProviderError("DeepSeek JSON response must be an object.")
        return result
