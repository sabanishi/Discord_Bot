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
import bot_jobs
from jobs import run_check_job, run_create_job


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
        self.original_notifier = main.notifier
        self.original_runtime = main.runtime
        main.runtime = types.SimpleNamespace(
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
            ),
        )
        main.notifier = self.notifier
        main.DEFAULT_CHANNEL_ID = 123
        main.ALERT_CHANNEL_ID = 456
        main.COSENSE_PROJECT = "project"

    def tearDown(self):
        main.notifier = self.original_notifier
        main.runtime = self.original_runtime

    def test_create_job_notifies_created_page_url(self):
        asyncio.run(run_create_job(main.runtime, self.notifier, datetime(2026, 10, 1)))

        self.assertEqual(len(self.notifier.messages), 1)
        channel_id, message = self.notifier.messages[0]
        self.assertEqual(channel_id, 123)
        self.assertIn("https://scrapbox.io/project/2026-10-01", message)
        self.assertEqual(self.diary.created[0], "2026-10-01")

    def test_check_job_notifies_only_when_page_is_unchanged(self):
        with patch("jobs.normalize_lines", return_value=["same"]):
            asyncio.run(run_check_job(main.runtime, self.notifier, datetime(2026, 10, 1)))

        self.assertEqual(len(self.notifier.messages), 1)
        self.assertEqual(self.notifier.messages[0][0], 456)
        self.assertIn("日記が更新されていません", self.notifier.messages[0][1])

    def test_check_job_does_not_notify_when_page_has_changed(self):
        with patch("jobs.normalize_lines", side_effect=[["expected"], ["actual"]]):
            asyncio.run(run_check_job(main.runtime, self.notifier, datetime(2026, 10, 1)))

        self.assertEqual(self.notifier.messages, [])

    def test_main_calls_startup_steps_in_order_with_loaded_token(self):
        events = []
        with patch.object(main, "initialize_runtime", side_effect=lambda: events.append("initialize")), \
             patch.object(main, "validate_runtime_env", side_effect=lambda state: events.append("validate")), \
             patch.object(main, "register_tactical_challenge_api", side_effect=lambda: events.append("api")), \
             patch.object(main, "start_web_server", side_effect=lambda: events.append("web")), \
             patch.object(main.client, "run", side_effect=lambda token: events.append(f"run:{token}")), \
             patch.object(main.runtime, "config", types.SimpleNamespace(token="token")):
            main.main()

        self.assertEqual(events, ["initialize", "validate", "api", "web", "run:token"])

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
        original_runtime = main.runtime
        try:
            initialized = types.SimpleNamespace(
                config=config,
                link_warning_state=object(),
                diary_client=object(),
            )
            with patch.object(main, "build_runtime", return_value=initialized):
                main.runtime = types.SimpleNamespace()
                main.initialize_runtime()

            self.assertIs(main.runtime, initialized)
        finally:
            main.runtime = original_runtime

    def test_on_ready_creates_session_and_registers_tasks_only_once(self):
        class Session:
            closed = False

        created_tasks = []
        original_runtime = main.runtime
        original_loop = getattr(main.client, "loop", None)
        try:
            main.runtime = types.SimpleNamespace(
                http_session=None,
                diary_client=types.SimpleNamespace(session=None),
                config=types.SimpleNamespace(link_warning_enabled=True),
                tasks_started=False,
            )
            main.client.loop = types.SimpleNamespace(
                create_task=lambda coroutine: (created_tasks.append(coroutine), coroutine.close())
            )
            with patch("main.aiohttp.ClientSession", return_value=Session()) as session_class:
                asyncio.run(main.on_ready())
                asyncio.run(main.on_ready())

            session_class.assert_called_once_with()
            self.assertEqual(len(created_tasks), 4)
            self.assertIs(main.runtime.diary_client.session, main.runtime.http_session)
        finally:
            main.runtime = original_runtime
            if original_loop is not None:
                main.client.loop = original_loop

    def test_on_disconnect_closes_session_and_stops_web_server(self):
        class Session:
            closed = False

            async def close(self):
                self.closed = True

        session = Session()
        original_runtime = main.runtime
        try:
            main.runtime = types.SimpleNamespace(http_session=session)
            with patch("main.stop_web_server") as stop_server:
                asyncio.run(main.on_disconnect())

            self.assertTrue(session.closed)
            stop_server.assert_called_once_with()
        finally:
            main.runtime = original_runtime

    def test_job_loops_pass_runtime_schedule_to_common_scheduler(self):
        async def capture(**kwargs):
            captured.append(kwargs)

        original_runtime = main.runtime
        captured = []
        try:
            main.runtime = types.SimpleNamespace(
                http_session=None,
                diary_client=self.diary,
                link_warning_state=None,
                config=types.SimpleNamespace(
                    create_page_time=(6, 30),
                    check_page_time=(21, 15),
                    link_warning_interval_minutes=10,
                    link_warning_enabled=True,
                    default_channel_id=123,
                    alert_channel_id=456,
                    mention_target="",
                    cosense_project="project",
                    cosense_sid="sid",
                ),
            )
            with patch("bot_jobs.run_daily_loop", side_effect=capture), \
                 patch("bot_jobs.run_interval_loop", side_effect=capture), \
                 patch.object(main.client, "wait_until_ready", new_callable=AsyncMock):
                asyncio.run(bot_jobs.create_page_loop(main.client, main.runtime, main.notifier))
                asyncio.run(bot_jobs.check_page_loop(main.client, main.runtime, main.notifier))
                asyncio.run(bot_jobs.tactical_challenge_loop(main.client, main.runtime, main.notifier))
                asyncio.run(bot_jobs.link_warning_loop(main.client, main.runtime, main.notifier))

            self.assertEqual(
                [(item["hour"], item["minute"]) for item in captured[:3]],
                [(6, 30), (21, 15), (21, 15)],
            )
            self.assertEqual(captured[3]["interval_seconds"], 600)
            self.assertTrue(all(callable(item["job"]) for item in captured))
            self.assertTrue(all(callable(item["on_error"]) for item in captured))
        finally:
            main.runtime = original_runtime


if __name__ == "__main__":
    unittest.main()
