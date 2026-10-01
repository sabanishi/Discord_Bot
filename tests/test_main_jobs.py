import asyncio
import sys
import types
import unittest
from datetime import datetime
from unittest.mock import patch


class FakeDiscordClient:
    def __init__(self, *args, **kwargs):
        pass

    def run(self, token):
        pass

    def event(self, function):
        return function


fake_discord = types.SimpleNamespace(
    Client=FakeDiscordClient,
    HTTPException=type("HTTPException", (Exception,), {}),
    Intents=types.SimpleNamespace(default=lambda: object()),
)
sys.modules.setdefault("discord", fake_discord)

import main


class FakeDiaryClient:
    async def create_page(self, title, lines):
        self.created = (title, lines)
        return "https://scrapbox.io/project/2026-10-01"

    async def fetch_page_lines(self, title):
        return [title, "記入済み"]


class FakeNotifier:
    def __init__(self):
        self.messages = []

    async def send(self, channel_id, message):
        self.messages.append((channel_id, message))
        return True


class MainJobTests(unittest.TestCase):
    def setUp(self):
        self.diary = FakeDiaryClient()
        self.notifier = FakeNotifier()
        self.original_diary = main.diary_client
        self.original_notifier = main.notifier
        self.original_default = main.DEFAULT_CHANNEL_ID
        self.original_alert = main.ALERT_CHANNEL_ID
        self.original_project = main.COSENSE_PROJECT
        main.diary_client = self.diary
        main.notifier = self.notifier
        main.DEFAULT_CHANNEL_ID = 123
        main.ALERT_CHANNEL_ID = 456
        main.COSENSE_PROJECT = "project"

    def tearDown(self):
        main.diary_client = self.original_diary
        main.notifier = self.original_notifier
        main.DEFAULT_CHANNEL_ID = self.original_default
        main.ALERT_CHANNEL_ID = self.original_alert
        main.COSENSE_PROJECT = self.original_project

    def test_create_job_notifies_created_page_url(self):
        asyncio.run(main.run_create_job(datetime(2026, 10, 1)))

        self.assertEqual(len(self.notifier.messages), 1)
        channel_id, message = self.notifier.messages[0]
        self.assertEqual(channel_id, 123)
        self.assertIn("https://scrapbox.io/project/2026-10-01", message)
        self.assertEqual(self.diary.created[0], "2026-10-01")

    def test_check_job_notifies_only_when_page_is_unchanged(self):
        with patch.object(main, "normalize_lines", return_value=["same"]):
            asyncio.run(main.run_check_job(datetime(2026, 10, 1)))

        self.assertEqual(len(self.notifier.messages), 1)
        self.assertEqual(self.notifier.messages[0][0], 456)
        self.assertIn("日記が更新されていません", self.notifier.messages[0][1])

    def test_check_job_does_not_notify_when_page_has_changed(self):
        with patch.object(main, "normalize_lines", side_effect=[["expected"], ["actual"]]):
            asyncio.run(main.run_check_job(datetime(2026, 10, 1)))

        self.assertEqual(self.notifier.messages, [])

    def test_main_calls_startup_steps_in_order_with_loaded_token(self):
        events = []
        config = types.SimpleNamespace(token="token")

        with patch.object(main, "initialize_runtime", side_effect=lambda: events.append("initialize")), \
             patch.object(main, "validate_env", side_effect=lambda: events.append("validate")), \
             patch.object(main, "register_tactical_challenge_api", side_effect=lambda: events.append("api")), \
             patch.object(main, "start_web_server", side_effect=lambda: events.append("web")), \
             patch.object(main.client, "run", side_effect=lambda token: events.append(f"run:{token}")), \
             patch.object(main, "TOKEN", "token"):
            main.main()

        self.assertEqual(events, ["initialize", "validate", "api", "web", "run:token"])


if __name__ == "__main__":
    unittest.main()
