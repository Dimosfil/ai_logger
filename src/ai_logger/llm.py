from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
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


@dataclass(frozen=True)
class CodexAppServerOptions:
    command: str = ""
    model: str = "gpt-codex-spark-high"
    effort: str = "high"
    cwd: str = ""
    request_timeout_seconds: float = 30.0
    turn_timeout_seconds: float = 180.0
    developer_instructions: str = (
        "You are a local log-search analysis provider. "
        "Answer in chat only. Return only a JSON object. "
        "Do not edit files, inspect files, run shell commands, or ask for approvals."
    )


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


class CodexAppServerChatClient:
    """Local Codex app-server JSON client for log-search analysis."""

    def __init__(self, options: CodexAppServerOptions, runner: Any | None = None) -> None:
        self.options = options
        self._runner = runner

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "CodexAppServerChatClient":
        env = environ or os.environ
        return cls(
            CodexAppServerOptions(
                command=resolve_codex_command(env),
                model=env.get("AI_LOGGER_CODEX_MODEL")
                or env.get("CODEX_MODEL")
                or env.get("LLM_MODEL")
                or "gpt-codex-spark-high",
                effort=normalize_codex_effort(
                    env.get("AI_LOGGER_CODEX_EFFORT") or env.get("CODEX_EFFORT")
                ),
                cwd=env.get("AI_LOGGER_CODEX_CWD") or env.get("CODEX_CWD") or os.getcwd(),
                request_timeout_seconds=float(
                    env.get("AI_LOGGER_CODEX_REQUEST_TIMEOUT_SECONDS")
                    or env.get("CODEX_REQUEST_TIMEOUT_SECONDS")
                    or "30"
                ),
                turn_timeout_seconds=float(
                    env.get("AI_LOGGER_CODEX_TURN_TIMEOUT_SECONDS")
                    or env.get("CODEX_TURN_TIMEOUT_SECONDS")
                    or "180"
                ),
            )
        )

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        prompt = "\n\n".join(
            [
                "Return only valid JSON with shape:",
                '{"summary": string, "matches": [{"id": string, "reason": string}]}',
                "Do not include Markdown fences or commentary.",
                f"System instructions:\n{system_prompt}",
                f"User payload:\n{user_prompt}",
            ]
        )
        try:
            output = (
                self._runner(prompt, self.options)
                if self._runner
                else run_codex_app_server_turn(prompt, self.options)
            )
        except Exception as exc:  # pragma: no cover - process failures vary by machine.
            raise LlmProviderError(f"Codex app-server request failed: {exc}") from exc
        return parse_json_object_output(output, "Codex app-server")


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


def normalize_codex_effort(value: str | None) -> str:
    effort = (value or "").strip().lower()
    return effort if effort in {"low", "medium", "high"} else "high"


def resolve_codex_command(env: Mapping[str, str] | None = None) -> str:
    values = env or os.environ
    command = values.get("AI_LOGGER_CODEX_COMMAND") or values.get("CODEX_COMMAND")
    if command and command.strip():
        return command.strip()
    if os.name == "nt":
        userprofile = values.get("USERPROFILE")
        if not userprofile:
            try:
                userprofile = str(Path.home())
            except RuntimeError:
                userprofile = ""
        if userprofile:
            preferred = Path(userprofile) / ".codex" / "bin" / "codex.cmd"
            if preferred.exists():
                return str(preferred)
        return "codex.cmd"
    return "codex"


def run_codex_app_server_turn(prompt: str, options: CodexAppServerOptions) -> str:
    runtime = _CodexAppServerRuntime(options)
    try:
        runtime.start()
        thread_id = runtime.start_thread()
        return runtime.run_turn(thread_id, prompt)
    finally:
        runtime.stop()


class _CodexAppServerRuntime:
    def __init__(self, options: CodexAppServerOptions) -> None:
        self.options = options
        self.process: subprocess.Popen[str] | None = None
        self.next_id = 1
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.stderr_lines: list[str] = []

    def start(self) -> None:
        if not self.options.command:
            raise LlmProviderError("Codex command is not configured.")
        startupinfo = None
        if os.name == "nt":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self.process = subprocess.Popen(
            [self.options.command, "app-server"],
            cwd=self.options.cwd or None,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            startupinfo=startupinfo,
        )
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        self._request(
            "initialize",
            {
                "clientInfo": {
                    "name": "ai_logger_codex_app",
                    "title": "ai_logger Codex Log Search",
                    "version": "0.1.0",
                },
                "capabilities": {
                    "experimentalApi": True,
                    "requestAttestation": False,
                    "optOutNotificationMethods": [
                        "command/exec/outputDelta",
                        "item/plan/delta",
                        "item/fileChange/outputDelta",
                        "item/reasoning/summaryTextDelta",
                        "item/reasoning/textDelta",
                    ],
                },
            },
        )
        self._notify("initialized", {})

    def stop(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.kill()

    def start_thread(self) -> str:
        result = self._request(
            "thread/start",
            {
                "model": self.options.model,
                "modelProvider": None,
                "cwd": self.options.cwd,
                "runtimeWorkspaceRoots": [self.options.cwd],
                "approvalPolicy": None,
                "approvalsReviewer": None,
                "sandbox": None,
                "permissions": None,
                "config": None,
                "serviceName": None,
                "baseInstructions": None,
                "developerInstructions": self.options.developer_instructions,
                "personality": None,
                "ephemeral": True,
                "sessionStartSource": None,
                "threadSource": None,
                "environments": None,
                "dynamicTools": None,
                "selectedCapabilityRoots": None,
                "mockExperimentalField": None,
            },
        )
        thread_id = ((result or {}).get("thread") or {}).get("id")
        if not thread_id:
            raise LlmProviderError("Codex app-server did not return a thread id.")
        return str(thread_id)

    def run_turn(self, thread_id: str, prompt: str) -> str:
        result = self._request(
            "turn/start",
            {
                "threadId": thread_id,
                "clientUserMessageId": str(uuid.uuid4()),
                "input": [{"type": "text", "text": prompt, "text_elements": []}],
                "responsesapiClientMetadata": None,
                "additionalContext": None,
                "environments": None,
                "cwd": self.options.cwd,
                "runtimeWorkspaceRoots": [self.options.cwd],
                "approvalPolicy": None,
                "approvalsReviewer": None,
                "sandboxPolicy": None,
                "permissions": None,
                "model": None,
                "effort": self.options.effort,
                "summary": None,
                "personality": None,
                "outputSchema": None,
                "collaborationMode": None,
            },
        )
        turn_id = ((result or {}).get("turn") or {}).get("id")
        return self._collect_final_response(turn_id)

    def _send(self, message: Mapping[str, Any]) -> None:
        if not self.process or not self.process.stdin:
            raise LlmProviderError("Codex app-server is not running.")
        self.process.stdin.write(json.dumps(message, ensure_ascii=False) + "\n")
        self.process.stdin.flush()

    def _notify(self, method: str, params: Mapping[str, Any]) -> None:
        self._send({"method": method, "params": dict(params)})

    def _request(self, method: str, params: Mapping[str, Any]) -> dict[str, Any]:
        request_id = self.next_id
        self.next_id += 1
        self._send({"method": method, "id": request_id, "params": dict(params)})
        while True:
            message = self._next_message(
                self.options.request_timeout_seconds,
                f"Codex response {request_id}",
            )
            if message.get("id") != request_id:
                continue
            if message.get("error"):
                raise LlmProviderError(f"Codex request failed: {message['error']}")
            result = message.get("result")
            return result if isinstance(result, dict) else {}

    def _collect_final_response(self, turn_id: str | None) -> str:
        streamed = ""
        completed_text = ""
        while True:
            message = self._next_message(
                self.options.turn_timeout_seconds,
                "Codex turn completion",
            )
            method = message.get("method")
            params = message.get("params") if isinstance(message.get("params"), dict) else {}
            if method == "item/agentMessage/delta":
                delta = params.get("delta") if isinstance(params.get("delta"), str) else params.get("text")
                if isinstance(delta, str):
                    streamed += delta
            if method == "item/completed":
                item = params.get("item") if isinstance(params.get("item"), dict) else {}
                if item.get("type") == "agentMessage" and isinstance(item.get("text"), str):
                    completed_text = item["text"]
            if method == "turn/completed":
                completed_turn = params.get("turn") if isinstance(params.get("turn"), dict) else {}
                if not turn_id or completed_turn.get("id") == turn_id:
                    output = (completed_text or streamed).strip()
                    if not output:
                        raise LlmProviderError("Codex app-server returned an empty response.")
                    return output

    def _next_message(self, timeout_seconds: float, context: str) -> dict[str, Any]:
        try:
            return self.messages.get(timeout=timeout_seconds)
        except queue.Empty as exc:
            raise LlmProviderError(f"Timed out while waiting for {context}.{self._stderr_tail()}") from exc

    def _read_stdout(self) -> None:
        assert self.process and self.process.stdout
        for line in self.process.stdout:
            text = line.strip()
            if not text:
                continue
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                self._append_stderr(text)
                continue
            if isinstance(payload, dict):
                self.messages.put(payload)

    def _read_stderr(self) -> None:
        assert self.process and self.process.stderr
        for line in self.process.stderr:
            self._append_stderr(line.rstrip())

    def _append_stderr(self, line: str) -> None:
        if not line:
            return
        self.stderr_lines.append(line)
        if len(self.stderr_lines) > 80:
            self.stderr_lines.pop(0)

    def _stderr_tail(self) -> str:
        return f" Stderr: {' '.join(self.stderr_lines)}" if self.stderr_lines else ""


def parse_json_object_output(output: str, provider_name: str) -> dict[str, Any]:
    text = output.strip()
    if text.startswith("```"):
        text = _strip_json_fence(text)
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LlmProviderError(f"{provider_name} response content was not valid JSON.") from exc
    if not isinstance(result, dict):
        raise LlmProviderError(f"{provider_name} JSON response must be an object.")
    return result


def _strip_json_fence(text: str) -> str:
    lines = text.splitlines()
    if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].strip() == "```":
        return "\n".join(lines[1:-1]).strip()
    return text


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
