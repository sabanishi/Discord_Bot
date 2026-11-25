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
    Intents=SimpleNamespace(default=lambda: SimpleNamespace(message_content=False)),
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

    def test_client_reads_message_content(self):
        state = SimpleNamespace(config=SimpleNamespace())
        with patch("app.discord_bot.discord.Client") as client_factory:
            DiscordBot(state, SimpleNamespace())

        intents = client_factory.call_args.kwargs["intents"]
        self.assertTrue(intents.message_content)


class DiscordBotBookmarkTests(unittest.IsolatedAsyncioTestCase):
    def make_bot(self, bookmark_channel_id):
        state = SimpleNamespace(
            http_session="session",
            config=SimpleNamespace(
                bookmark_channel_id=bookmark_channel_id,
                alert_channel_id=99,
                cosense_project="project",
                cosense_sid="sid",
                gyazo_access_token="gyazo",
            ),
        )
        with patch("app.discord_bot.discord.Client"):
            bot = DiscordBot(state, SimpleNamespace())
        bot.client.user = SimpleNamespace(id=1)
        return bot

    def make_message(self, channel_id, author):
        return SimpleNamespace(channel=SimpleNamespace(id=channel_id), author=author)

    async def test_bookmark_channel_message_is_handled(self):
        bot = self.make_bot(10)
        message = self.make_message(10, SimpleNamespace(id=2))
        with patch("app.discord_bot.build_bookmark_service") as build, patch(
            "app.discord_bot.handle_bookmark_message", new_callable=AsyncMock
        ) as handle:
            await bot.on_message(message)

        build.assert_called_once_with("project", "sid", "gyazo", "session")
        handle.assert_awaited_once_with(message, build.return_value, bot.notifier, 99)

    async def test_other_channels_and_own_messages_are_ignored(self):
        cases = [
            (10, self.make_message(11, SimpleNamespace(id=2))),
            (0, self.make_message(0, SimpleNamespace(id=2))),
        ]
        for channel_id, message in cases:
            with self.subTest(channel_id=channel_id):
                bot = self.make_bot(channel_id)
                with patch(
                    "app.discord_bot.handle_bookmark_message", new_callable=AsyncMock
                ) as handle:
                    await bot.on_message(message)
                handle.assert_not_awaited()

        bot = self.make_bot(10)
        own = self.make_message(10, bot.client.user)
        with patch("app.discord_bot.handle_bookmark_message", new_callable=AsyncMock) as handle:
            await bot.on_message(own)
        handle.assert_not_awaited()
