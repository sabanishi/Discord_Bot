import aiohttp
import discord
from app.bookmark import build_bookmark_service, handle_bookmark_message
from app.bot_jobs import register_scheduled_tasks
from app.notifications import DiscordNotifier
from app.runtime import RuntimeState
from app.web_server import WebServer


class DiscordBot:
    def __init__(self, state: RuntimeState, web_server: WebServer):
        self.state = state
        self.web_server = web_server
        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.notifier = DiscordNotifier(self.client)
        self.client.event(self.on_ready)
        self.client.event(self.on_message)

    async def on_ready(self) -> None:
        """共有HTTPセッションを準備し、Discordの定期タスクを一度だけ登録する"""
        print("ログインしました", flush=True)
        if self.state.http_session is None or self.state.http_session.closed:
            self.state.http_session = aiohttp.ClientSession()
            self.state.diary_client.session = self.state.http_session
        register_scheduled_tasks(self.client, self.state, self.notifier)

    async def on_message(self, message: discord.Message) -> None:
        config = self.state.config
        if not config.bookmark_channel_id:
            return
        if message.channel.id != config.bookmark_channel_id:
            return
        if message.author == self.client.user:
            return
        service = build_bookmark_service(
            config.cosense_project,
            config.cosense_sid,
            config.gyazo_access_token,
            self.state.http_session,
        )
        await handle_bookmark_message(
            message, service, self.notifier, config.alert_channel_id
        )

    def run(self) -> None:
        self.client.run(self.state.config.token)
