from __future__ import annotations

import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ai_logger.telegram_bot import TelegramBot, token_from_env


class TelegramBotTests(unittest.TestCase):
    def test_token_selection(self):
        self.assertEqual(token_from_env({"BOT_TOKEN": " fallback "}), "fallback")
        self.assertEqual(token_from_env({"TELEGRAM_BOT_TOKEN": "primary", "BOT_TOKEN": "fallback"}), "primary")
        self.assertIsNone(token_from_env({}))

    def test_private_start_and_help_only(self):
        calls = []
        updates = [
            {"update_id": 1, "message": {"chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "text": "/start"}},
            {"update_id": 2, "message": {"chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "text": "/help@ai_loggerbot"}},
            {"update_id": 3, "message": {"chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "photo": [{}]}},
            {"update_id": 4, "message": {"chat": {"id": -5, "type": "group"}, "from": {"id": 7}, "text": "/start"}},
            {"update_id": 5, "message": {"chat": {"id": 7, "type": "private"}, "from": {"id": 7}, "text": "hi"}},
        ]

        def transport(method, payload):
            calls.append((method, payload))
            return updates if method == "getUpdates" and payload["offset"] == 0 else []

        bot = TelegramBot("test", transport=transport)
        bot.poll_once()
        bot.poll_once()
        self.assertEqual([name for name, _ in calls].count("sendMessage"), 2)
        self.assertEqual(calls[-1], ("getUpdates", {"offset": 6, "timeout": 5, "allowed_updates": ["message"]}))

    def test_identity_mismatch_does_not_poll(self):
        calls = []
        checked = threading.Event()

        def transport(method, payload):
            calls.append(method)
            checked.set()
            return {"username": "some_other_bot"}

        bot = TelegramBot("test", expected_username="ai_loggerbot", transport=transport)
        bot.start()
        try:
            self.assertTrue(checked.wait(1))
            deadline = time.monotonic() + 1
            while bot.status()["error"] is None and time.monotonic() < deadline:
                time.sleep(0.001)
            self.assertEqual(bot.status()["error"], "wrong_bot_token")
            self.assertEqual(calls, ["getMe"])
        finally:
            bot.stop()


if __name__ == "__main__":
    unittest.main()
