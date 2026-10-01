import aiohttp
import discord
from notifications import DiscordNotifier
from client_tasks import register_scheduled_tasks
from web_server import register_tactical_challenge_api, start_web_server, stop_web_server
from runtime import RuntimeState, initialize_runtime as build_runtime, validate_env as validate_runtime_env

client = discord.Client(intents=discord.Intents.default())
notifier = DiscordNotifier(client)


runtime = RuntimeState()


def initialize_runtime() -> None:
    global runtime
    initialized = build_runtime()
    runtime = initialized


@client.event
async def on_ready() -> None:
    print("ログインしました", flush=True)

    if runtime.http_session is None or runtime.http_session.closed:
        runtime.http_session = aiohttp.ClientSession()
        runtime.diary_client.session = runtime.http_session

    register_scheduled_tasks(client, runtime, notifier)


@client.event
async def on_disconnect() -> None:
    if runtime.http_session is not None and not runtime.http_session.closed:
        await runtime.http_session.close()
    stop_web_server()

def main() -> None:
    initialize_runtime()
    validate_runtime_env(runtime)
    register_tactical_challenge_api()
    start_web_server()
    client.run(runtime.config.token)


if __name__ == "__main__":
    main()
