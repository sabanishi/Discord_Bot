import aiohttp
import discord

from app.bot_jobs import register_scheduled_tasks
from app.notifications import DiscordNotifier


class DiscordBot:
    def __init__(self, state, web_server):
        self.state = state
        self.web_server = web_server
        self.client = discord.Client(intents=discord.Intents.default())
        self.notifier = DiscordNotifier(self.client)
        self.client.event(self.on_ready)
        self.client.event(self.on_disconnect)

    async def on_ready(self) -> None:
        print("ログインしました", flush=True)
        if self.state.http_session is None or self.state.http_session.closed:
            self.state.http_session = aiohttp.ClientSession()
            self.state.diary_client.session = self.state.http_session
        register_scheduled_tasks(self.client, self.state, self.notifier)

    async def on_disconnect(self) -> None:
        if self.state.http_session is not None and not self.state.http_session.closed:
            await self.state.http_session.close()
        self.web_server.stop()

    def run(self) -> None:
        self.client.run(self.state.config.token)
