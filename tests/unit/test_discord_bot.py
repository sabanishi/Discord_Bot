import unittest
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

class FakeDiscordClient:
    def __init__(self, *args, **kwargs):
        self.loop = SimpleNamespace(create_task=lambda coroutine: coroutine.close())

    def event(self, function):
        return function


sys.modules.setdefault("discord", types.SimpleNamespace(
    Client=FakeDiscordClient,
    HTTPException=type("HTTPException", (Exception,), {}),
    Intents=SimpleNamespace(default=lambda: object()),
))

from app.discord_bot import DiscordBot


class DiscordBotTests(unittest.IsolatedAsyncioTestCase):
    async def test_ready_creates_shared_session_and_registers_tasks(self):
        state = SimpleNamespace(
            http_session=None,
            diary_client=SimpleNamespace(session=None),
            config=SimpleNamespace(link_warning_enabled=False),
        )
        with patch("app.discord_bot.aiohttp.ClientSession") as session_factory, patch(
            "app.discord_bot.register_scheduled_tasks"
        ) as register:
            web_server = SimpleNamespace(stop=lambda: None)
            bot = DiscordBot(state, web_server)
            await bot.on_ready()

        self.assertIs(state.http_session, session_factory.return_value)
        self.assertIs(state.diary_client.session, state.http_session)
        register.assert_called_once_with(bot.client, state, bot.notifier)
