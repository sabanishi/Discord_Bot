import aiohttp
import discord
from app.bot_jobs import register_scheduled_tasks
from app.notifications import DiscordNotifier
from app.runtime import RuntimeState
from app.web_server import WebServer


class DiscordBot:
    def __init__(self, state: RuntimeState, web_server: WebServer):
        self.state = state
        self.web_server = web_server
        self.client = discord.Client(intents=discord.Intents.default())
        self.notifier = DiscordNotifier(self.client)
        self.client.event(self.on_ready)

    async def on_ready(self) -> None:
        """共有HTTPセッションを準備し、Discordの定期タスクを一度だけ登録する"""
        print("ログインしました", flush=True)
        if self.state.http_session is None or self.state.http_session.closed:
            self.state.http_session = aiohttp.ClientSession()
            self.state.diary_client.session = self.state.http_session
        register_scheduled_tasks(self.client, self.state, self.notifier)

    def run(self) -> None:
        self.client.run(self.state.config.token)
