import asyncio
import unittest
from unittest.mock import patch

from app.notifications import DiscordNotifier


class FakeChannel:
    def __init__(self):
        self.messages = []

    async def send(self, message):
        self.messages.append(message)


class FakeClient:
    def __init__(self, channel):
        self.channel = channel

    def get_channel(self, channel_id):
        return self.channel


class NotificationTests(unittest.TestCase):
    def test_send_truncates_messages_to_1800_characters(self):
        channel = FakeChannel()
        notifier = DiscordNotifier(FakeClient(channel))

        result = asyncio.run(notifier.send(123, "x" * 2000))

        self.assertTrue(result)
        self.assertTrue(channel.messages[0].startswith("x" * 1800))
        self.assertTrue(channel.messages[0].endswith("\n...(長すぎるため省略しました)"))

    def test_send_returns_false_when_channel_is_missing(self):
        notifier = DiscordNotifier(FakeClient(None))

        with patch("builtins.print") as print_mock:
            result = asyncio.run(notifier.send(123, "message"))

        self.assertFalse(result)
        print_mock.assert_called_once()

    def test_send_returns_false_when_channel_send_fails(self):
        class FailingChannel:
            async def send(self, message):
                raise RuntimeError("send failed")

        notifier = DiscordNotifier(FakeClient(FailingChannel()))

        with patch("builtins.print") as print_mock:
            result = asyncio.run(notifier.send(123, "message"))

        self.assertFalse(result)
        self.assertIn("send failed", print_mock.call_args.args[0])

    def test_send_handles_discord_http_exception(self):
        http_error = fake_http_exception = type("HTTPException", (Exception,), {})
        import app.notifications as notifications

        original = notifications.discord
        notifications.discord = type("Discord", (), {"HTTPException": http_error})

        class FailingChannel:
            async def send(self, message):
                raise http_error("discord failed")

        try:
            notifier = DiscordNotifier(FakeClient(FailingChannel()))
            with patch("builtins.print") as print_mock:
                result = asyncio.run(notifier.send(123, "message"))
        finally:
            notifications.discord = original

        self.assertFalse(result)
        self.assertIn("Discordへのメッセージ送信に失敗しました", print_mock.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
