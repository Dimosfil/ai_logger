"""Minimal Telegram long-polling bot alongside the HTTP logger."""

from __future__ import annotations

import json
from threading import Event, Thread
from typing import Any, Callable, Mapping
from urllib import error, request


class TelegramApiError(RuntimeError):
    """A sanitized Telegram transport failure."""


class TelegramPollingConflict(TelegramApiError):
    """Another poller or a webhook owns this bot token."""


def token_from_env(environ: Mapping[str, str]) -> str | None:
    return (environ.get("TELEGRAM_BOT_TOKEN") or environ.get("BOT_TOKEN") or "").strip() or None


class TelegramBot:
    def __init__(
        self,
        token: str,
        *,
        expected_username: str | None = None,
        transport: Callable[[str, dict[str, Any]], Any] | None = None,
    ) -> None:
        if not token:
            raise ValueError("Telegram bot token is required")
        self._token = token
        self._transport = transport or self._request
        self._expected_username = expected_username.lstrip("@").lower() if expected_username else None
        self._verified = False
        self._offset = 0
        self._stop = Event()
        self._thread: Thread | None = None
        self._last_error: str | None = None

    def _request(self, method: str, payload: dict[str, Any]) -> Any:
        body = json.dumps(payload).encode("utf-8")
        api_request = request.Request(
            f"https://api.telegram.org/bot{self._token}/{method}",
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8"},
            method="POST",
        )
        try:
            with request.urlopen(api_request, timeout=15) as response:
                result = json.load(response)
        except error.HTTPError as exc:
            if exc.code == 409:
                raise TelegramPollingConflict("Telegram polling conflict") from None
            raise TelegramApiError("Telegram API unavailable") from None
        except (error.URLError, TimeoutError, ValueError):
            raise TelegramApiError("Telegram API unavailable") from None
        if not isinstance(result, dict) or not result.get("ok"):
            raise TelegramApiError("Telegram API unavailable")
        return result.get("result")

    def poll_once(self) -> None:
        updates = self._transport(
            "getUpdates",
            {"offset": self._offset, "timeout": 5, "allowed_updates": ["message"]},
        )
        if not isinstance(updates, list):
            raise TelegramApiError("Telegram updates unavailable")
        for update in updates:
            if not isinstance(update, dict):
                continue
            update_id = update.get("update_id")
            if type(update_id) is not int or update_id < self._offset:
                continue
            message = update.get("message")
            if isinstance(message, dict) and self._is_private_message(message):
                words = str(message.get("text") or "").split(maxsplit=1)
                command = words[0].split("@", maxsplit=1)[0].lower() if words else ""
                if command in ("/start", "/help"):
                    self._transport(
                        "sendMessage",
                        {"chat_id": message["chat"]["id"], "text": "ai_logger работает."},
                    )
            self._offset = update_id + 1

    @staticmethod
    def _is_private_message(message: dict[str, Any]) -> bool:
        chat = message.get("chat")
        sender = message.get("from")
        return (
            isinstance(chat, dict)
            and isinstance(sender, dict)
            and chat.get("type") == "private"
            and chat.get("id") == sender.get("id")
        )

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = Thread(target=self._run, name="ai-logger-telegram", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                if self._expected_username and not self._verified:
                    account = self._transport("getMe", {})
                    if not isinstance(account, dict) or str(account.get("username") or "").lower() != self._expected_username:
                        self._last_error = "wrong_bot_token"
                        self._stop.wait(30)
                        continue
                    self._verified = True
                self.poll_once()
                self._last_error = None
            except TelegramPollingConflict:
                self._last_error = "poll_conflict"
                self._stop.wait(5)
            except TelegramApiError:
                self._last_error = "api_unavailable"
                self._stop.wait(3)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=16)

    def status(self) -> dict[str, Any]:
        return {
            "configured": True,
            "running": bool(self._thread and self._thread.is_alive()),
            "error": self._last_error,
        }
