import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.bot_jobs import register_scheduled_tasks


class ClientTaskRegistrationTests(unittest.TestCase):
    def test_registers_daily_tasks_once_and_optional_link_warning(self):
        created = []
        client = SimpleNamespace(loop=SimpleNamespace(create_task=created.append))
        state = SimpleNamespace(config=SimpleNamespace(link_warning_enabled=True))
        notifier = object()

        loop_factory = Mock(return_value=object())
        with patch("app.bot_jobs.create_page_loop", new=loop_factory), patch(
            "app.bot_jobs.check_page_loop", new=loop_factory
        ), patch("app.bot_jobs.tactical_challenge_loop", new=loop_factory), patch(
            "app.bot_jobs.link_warning_loop", new=loop_factory
        ):
            self.assertTrue(register_scheduled_tasks(client, state, notifier))
            self.assertFalse(register_scheduled_tasks(client, state, notifier))

        self.assertEqual(len(created), 4)

    def test_registers_mirroring_at_three_daily_hours(self):
        created = []
        client = SimpleNamespace(loop=SimpleNamespace(create_task=created.append))
        state = SimpleNamespace(
            config=SimpleNamespace(
                link_warning_enabled=False,
                mirror_run_hours=(8, 16, 0),
            ),
            mirror_service=object(),
        )
        notifier = object()

        loop_factory = Mock(return_value=object())
        mirror_loop = Mock(return_value=object())
        with patch("app.bot_jobs.create_page_loop", new=loop_factory), patch(
            "app.bot_jobs.check_page_loop", new=loop_factory
        ), patch("app.bot_jobs.tactical_challenge_loop", new=loop_factory), patch(
            "app.bot_jobs.mirror_loop", new=mirror_loop
        ):
            self.assertTrue(register_scheduled_tasks(client, state, notifier))

        self.assertFalse(register_scheduled_tasks(client, state, notifier))

        self.assertEqual(mirror_loop.call_count, 3)
        self.assertEqual(
            [call.args[3:] for call in mirror_loop.call_args_list],
            [(8,), (16,), (0,)],
        )
