from __future__ import annotations

try:
    import discord
except ModuleNotFoundError:  # 単体テストで通知クライアントだけを検証する場合に許容する
    discord = None


class DiscordNotifier:
    def __init__(self, client: discord.Client):
        self.client = client

    async def send(self, channel_id: int, message: str) -> bool:
        channel = self.client.get_channel(channel_id)
        if channel is None:
            print(f"チャンネルが見つかりません:\n{channel_id}", flush=True)
            return False

        if len(message) > 1800:
            message = f"{message[:1800]}\n...(長すぎるため省略しました)"

        try:
            await channel.send(message)
            return True
        except Exception as error:
            if discord is not None and isinstance(error, discord.HTTPException):
                print(
                    f"Discordへのメッセージ送信に失敗しました:\n{error}",
                    flush=True,
                )
                return False
            print(
                f"Discordへのメッセージ送信で予期しないエラーが発生しました:\n{error}",
                flush=True,
            )
            return False
