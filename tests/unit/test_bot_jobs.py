import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.bot_jobs import create_page_loop


class BotJobLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_create_page_loop_uses_configured_time_and_job(self):
        client = SimpleNamespace(
            wait_until_ready=AsyncMock(),
            is_closed=lambda: False,
        )
        state = SimpleNamespace(config=SimpleNamespace(create_page_time=(7, 30), alert_channel_id=1, mention_target="@u"))
        notifier = SimpleNamespace(send=AsyncMock())

        with patch("app.bot_jobs.run_daily_loop", new=AsyncMock()) as scheduler, patch(
            "app.bot_jobs.run_create_job", new=AsyncMock()
        ):
            await create_page_loop(client, state, notifier)

        self.assertIs(scheduler.await_args.kwargs["wait_until_ready"], client.wait_until_ready)
        self.assertIs(scheduler.await_args.kwargs["is_closed"], client.is_closed)
        self.assertEqual(scheduler.await_args.kwargs["hour"], 7)
        self.assertEqual(scheduler.await_args.kwargs["minute"], 30)
        self.assertTrue(callable(scheduler.await_args.kwargs["job"]))
        self.assertTrue(callable(scheduler.await_args.kwargs["on_error"]))
