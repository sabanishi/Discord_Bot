import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.bot_jobs import create_page_loop, mirror_loop


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

    async def test_mirror_loop_runs_service_and_notifies_errors(self):
        client = SimpleNamespace(
            wait_until_ready=AsyncMock(),
            is_closed=lambda: False,
        )
        service = SimpleNamespace(run=AsyncMock())
        state = SimpleNamespace(
            mirror_service=service,
            config=SimpleNamespace(alert_channel_id=10, mention_target="@u"),
        )
        notifier = SimpleNamespace(send=AsyncMock())

        with patch("app.bot_jobs.run_daily_loop", new=AsyncMock()) as scheduler:
            await mirror_loop(client, state, notifier, 16)

        self.assertEqual(scheduler.await_args.kwargs["hour"], 16)
        self.assertEqual(scheduler.await_args.kwargs["minute"], 0)
        await scheduler.await_args.kwargs["job"]("target")
        service.run.assert_awaited_once_with()
        await scheduler.await_args.kwargs["on_error"](RuntimeError("failed"))
        notifier.send.assert_awaited_once()
        self.assertIn("failed", notifier.send.await_args.args[1])
