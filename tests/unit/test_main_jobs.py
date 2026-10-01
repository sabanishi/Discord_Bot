import asyncio
import sys
import types
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, patch


class FakeDiscordClient:
    def __init__(self, *args, **kwargs):
        pass

    def run(self, token):
        pass

    async def wait_until_ready(self):
        pass

    def is_closed(self):
        return False

    def event(self, function):
        return function


fake_discord = types.SimpleNamespace(
    Client=FakeDiscordClient,
    HTTPException=type("HTTPException", (Exception,), {}),
    Intents=types.SimpleNamespace(default=lambda: object()),
)
sys.modules.setdefault("discord", fake_discord)

import main
import app.bot_jobs as bot_jobs
from app.jobs import run_check_job, run_create_job


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
        self.runtime = types.SimpleNamespace(
            diary_client=self.diary,
            link_warning_state=None,
            config=types.SimpleNamespace(
                default_channel_id=123,
                alert_channel_id=456,
                cosense_project="project",
                cosense_sid="sid",
                mention_target="",
                create_page_time=(7, 0),
                check_page_time=(21, 15),
                link_warning_enabled=False,
                link_warning_interval_minutes=30,
                validate_env=lambda: None,
            ),
        )
        main.DEFAULT_CHANNEL_ID = 123
        main.ALERT_CHANNEL_ID = 456
        main.COSENSE_PROJECT = "project"

    def test_create_job_notifies_created_page_url(self):
        asyncio.run(run_create_job(self.runtime, self.notifier, datetime(2026, 10, 1)))

        self.assertEqual(len(self.notifier.messages), 1)
        channel_id, message = self.notifier.messages[0]
        self.assertEqual(channel_id, 123)
        self.assertIn("https://scrapbox.io/project/2026-10-01", message)
        self.assertEqual(self.diary.created[0], "2026-10-01")

    def test_check_job_notifies_only_when_page_is_unchanged(self):
        with patch("app.jobs.normalize_lines", return_value=["same"]):
            asyncio.run(run_check_job(self.runtime, self.notifier, datetime(2026, 10, 1)))

        self.assertEqual(len(self.notifier.messages), 1)
        self.assertEqual(self.notifier.messages[0][0], 456)
        self.assertIn("日記が更新されていません", self.notifier.messages[0][1])

    def test_check_job_does_not_notify_when_page_has_changed(self):
        with patch("app.jobs.normalize_lines", side_effect=[["expected"], ["actual"]]):
            asyncio.run(run_check_job(self.runtime, self.notifier, datetime(2026, 10, 1)))

        self.assertEqual(self.notifier.messages, [])

    def test_main_calls_startup_steps_in_order_with_loaded_token(self):
        events = []
        runtime = types.SimpleNamespace(
            config=types.SimpleNamespace(token="token"),
        )
        with patch.object(main, "build_runtime", side_effect=lambda: (events.append("initialize"), runtime)[1]), \
             patch.object(main, "WebServer") as web_server_class, \
             patch.object(main, "DiscordBot") as discord_bot_class:
            web_server_class.return_value.start.side_effect=lambda: events.append("web")
            discord_bot_class.return_value.run.side_effect=lambda: events.append("run:token")
            main.main()

        self.assertEqual(events, ["initialize", "web", "run:token"])

    def test_initialize_runtime_builds_shared_runtime_state(self):
        config = types.SimpleNamespace(
            token="token",
            default_channel_id=123,
            alert_channel_id=456,
            cosense_project="project",
            cosense_sid="sid",
            mention_target="<@789>",
            create_page_time=(7, 0),
            check_page_time=(21, 15),
            link_warning_enabled=True,
            link_warning_interval_minutes=30,
            link_warning_threshold=30,
            link_warning_resolve_threshold=29,
            link_warning_config_page="除外設定",
        )
        initialized = types.SimpleNamespace(
                config=config,
                link_warning_state=object(),
                diary_client=object(),
            )
        with patch.object(main, "build_runtime", return_value=initialized):
            self.assertIs(main.build_runtime(), initialized)

    def test_job_loops_pass_runtime_schedule_to_common_scheduler(self):
        async def capture(**kwargs):
            captured.append(kwargs)

        captured = []
        client = types.SimpleNamespace(wait_until_ready=AsyncMock(), is_closed=lambda: False)
        self.runtime.config.create_page_time = (6, 30)
        self.runtime.config.check_page_time = (21, 15)
        self.runtime.config.link_warning_interval_minutes = 10
        self.runtime.config.link_warning_enabled = True
        with patch("app.bot_jobs.run_daily_loop", side_effect=capture), \
             patch("app.bot_jobs.run_interval_loop", side_effect=capture):
            asyncio.run(bot_jobs.create_page_loop(client, self.runtime, self.notifier))
            asyncio.run(bot_jobs.check_page_loop(client, self.runtime, self.notifier))
            asyncio.run(bot_jobs.tactical_challenge_loop(client, self.runtime, self.notifier))
            asyncio.run(bot_jobs.link_warning_loop(client, self.runtime, self.notifier))

        self.assertEqual(
            [(item["hour"], item["minute"]) for item in captured[:3]],
            [(6, 30), (21, 15), (21, 15)],
        )
        self.assertEqual(captured[3]["interval_seconds"], 600)
        self.assertTrue(all(callable(item["job"]) for item in captured))
        self.assertTrue(all(callable(item["on_error"]) for item in captured))


if __name__ == "__main__":
    unittest.main()
