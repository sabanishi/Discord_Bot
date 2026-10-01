from app.discord_bot import DiscordBot
from app.web_server import WebServer
from app.runtime import initialize_runtime as build_runtime


def main() -> None:
    runtime = build_runtime()
    web_server = WebServer()
    web_server.start()
    DiscordBot(runtime, web_server).run()


if __name__ == "__main__":
    main()
