import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.client_tasks import register_scheduled_tasks


class ClientTaskRegistrationTests(unittest.TestCase):
    def test_registers_daily_tasks_once_and_optional_link_warning(self):
        created = []
        client = SimpleNamespace(loop=SimpleNamespace(create_task=created.append))
        state = SimpleNamespace(config=SimpleNamespace(link_warning_enabled=True))
        notifier = object()

        with patch("app.client_tasks.create_page_loop"), patch("app.client_tasks.check_page_loop"), patch(
            "app.client_tasks.tactical_challenge_loop"
        ), patch("app.client_tasks.link_warning_loop"):
            self.assertTrue(register_scheduled_tasks(client, state, notifier))
            self.assertFalse(register_scheduled_tasks(client, state, notifier))

        self.assertEqual(len(created), 4)
