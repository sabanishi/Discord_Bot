import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.jobs import run_check_job, run_create_job


class JobTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_create_job_creates_page_and_notifies_url(self):
        state = SimpleNamespace(
            config=SimpleNamespace(default_channel_id=123),
            diary_client=SimpleNamespace(create_page=AsyncMock(return_value="https://example/page")),
        )
        notifier = SimpleNamespace(send=AsyncMock())

        with patch("app.jobs.build_page_from_template", return_value=("title", ["line"])):
            await run_create_job(state, notifier, SimpleNamespace())

        state.diary_client.create_page.assert_awaited_once_with("title", ["line"])
        notifier.send.assert_awaited_once_with(
            123,
            "おはようございます。今日の日記ページはこちらです。\nhttps://example/page",
        )

    async def test_run_check_job_notifies_when_page_is_unchanged(self):
        state = SimpleNamespace(
            config=SimpleNamespace(alert_channel_id=456, mention_target="@user", cosense_project="project"),
            diary_client=SimpleNamespace(fetch_page_lines=AsyncMock(return_value=["same"])),
        )
        notifier = SimpleNamespace(send=AsyncMock())

        with patch("app.jobs.build_page_from_template", return_value=("title", ["same"])), patch(
            "app.jobs.normalize_lines", side_effect=lambda lines: lines
        ):
            await run_check_job(state, notifier, SimpleNamespace())

        notifier.send.assert_awaited_once()
        self.assertIn("まだ日記が更新されていませんよ！", notifier.send.await_args.args[1])
