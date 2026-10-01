from datetime import datetime
from dataclasses import dataclass
from urllib.parse import quote

import aiohttp
import discord
from config import AppConfig, load_config, normalize_sid
from diary import DiaryClient, build_page_from_template, normalize_lines
from notifications import DiscordNotifier
from scheduling import run_daily_loop, run_interval_loop
from web_server import register_tactical_challenge_api, start_web_server, stop_web_server
from link_warning import LinkWarningState, ScrapboxLinkClient
from tactical_challenge.scheduler import (
    format_tactical_challenge_completion,
    format_tactical_challenge_error,
    run_tactical_challenge_once,
)

client = discord.Client(intents=discord.Intents.default())
notifier = DiscordNotifier(client)


@dataclass
class RuntimeState:
    config: AppConfig | None = None
    link_warning_state: LinkWarningState | None = None
    diary_client: DiaryClient | None = None
    http_session: aiohttp.ClientSession | None = None


runtime = RuntimeState()
daily_task_started = False


def initialize_runtime() -> None:
    config = load_config()
    runtime.config = config
    runtime.link_warning_state = LinkWarningState(
        warning_threshold=config.link_warning_threshold,
        resolve_threshold=config.link_warning_resolve_threshold,
    )
    runtime.diary_client = DiaryClient(config.cosense_project, config.cosense_sid)


def get_encoded_project() -> str:
    return quote(runtime.config.cosense_project, safe="")


def validate_env() -> None:
    config = runtime.config
    if not config.token:
        raise RuntimeError("環境変数 DISCORD_TOKEN が設定されていません")

    if not config.default_channel_id:
        raise RuntimeError("環境変数 DISCORD_DEFAULT_CHANNEL_ID が設定されていません")

    if not config.alert_channel_id:
        raise RuntimeError("環境変数 DISCORD_ALERT_CHANNEL_ID が設定されていません")

    if not config.cosense_project:
        raise RuntimeError("環境変数 COSENSE_PROJECT が設定されていません")

    if not config.cosense_sid:
        raise RuntimeError("環境変数 COSENSE_SID が設定されていません")


def get_page_url(title: str) -> str:
    encoded_project = get_encoded_project()
    encoded_title = quote(title, safe="")

    return f"https://scrapbox.io/{encoded_project}/{encoded_title}"


async def run_create_job(target: datetime) -> None:
    title, lines = build_page_from_template(target)
    page_url = await runtime.diary_client.create_page(title, lines)

    await notifier.send(
        runtime.config.default_channel_id,
        f"おはようございます。今日の日記ページはこちらです。\n{page_url}",
    )


async def run_check_job(target: datetime) -> None:
    title, expected_lines = build_page_from_template(target)
    actual_lines = await runtime.diary_client.fetch_page_lines(title)

    expected = normalize_lines(expected_lines)
    actual = normalize_lines(actual_lines)

    page_url = get_page_url(title)

    if actual == expected:
        await notifier.send(
            runtime.config.alert_channel_id,
            f"{runtime.config.mention_target}\n"
            f"もう、何やってたんですか！　まだ日記が更新されていませんよ！\n"
            f"早く済ませてください。\n"
            f"{page_url}",
        )


async def create_page_loop() -> None:
    async def job(target):
        print(f"Scrapboxページを作成します: {target}", flush=True)
        await run_create_job(target)

    async def on_error(error):
        print(f"ページ作成処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            runtime.config.alert_channel_id,
            f"{runtime.config.mention_target}\nScrapboxページが作成できませんでしたよ。\n"
            f"何かバグがあるんじゃないですか？:\n<エラーログ>\n{error}",
        )

    await run_daily_loop(
        client=client,
        hour=runtime.config.create_page_time[0],
        minute=runtime.config.create_page_time[1],
        job=job,
        on_error=on_error,
    )


async def check_page_loop() -> None:
    async def job(target):
        print(f"Scrapboxページの変更を確認します:\n{target}", flush=True)
        await run_check_job(target)

    async def on_error(error):
        print(f"ページ確認処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            runtime.config.alert_channel_id,
            f"{runtime.config.mention_target}\nああ、もう！日記がチェックできませんでしたよ！\n"
            f"ちゃんとプログラム書いてください！:\n<エラーログ>\n{error}",
        )

    await run_daily_loop(
        client=client,
        hour=runtime.config.check_page_time[0],
        minute=runtime.config.check_page_time[1],
        job=job,
        on_error=on_error,
    )


async def tactical_challenge_loop() -> None:
    """毎日21:15に戦術対抗戦ページをリファクタする。"""
    async def job(target):
        print(f"戦術対抗戦ページを更新します: {target}", flush=True)
        results = await run_tactical_challenge_once()
        await notifier.send(
            runtime.config.default_channel_id,
            format_tactical_challenge_completion(results),
        )

    async def on_error(error):
        print(f"戦術対抗戦ページ更新処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            runtime.config.alert_channel_id,
            f"{runtime.config.mention_target}\n{format_tactical_challenge_error(error)}",
        )

    await run_daily_loop(
        client=client,
        hour=runtime.config.check_page_time[0],
        minute=runtime.config.check_page_time[1],
        job=job,
        on_error=on_error,
    )


async def run_link_warning_check() -> None:
    cosense = ScrapboxLinkClient(
        project=runtime.config.cosense_project,
        sid=normalize_sid(runtime.config.cosense_sid),
        session=runtime.http_session,
    )
    pages = await cosense.fetch_page_summaries()
    excluded_titles = await cosense.fetch_excluded_titles(runtime.config.link_warning_config_page)
    candidates = runtime.link_warning_state.find_new_warnings(pages, excluded_titles)

    for page in candidates:
        page_url = get_page_url(page.title)
        sent = await notifier.send(
            runtime.config.alert_channel_id,
            f"{runtime.config.mention_target}\n"
            f"「{page.title}」が{page.linked_count}個のページから参照されているようですね。\n"
            f"そろそろ整理や分割を考えた方が良いんじゃないですか？\n"
            f"{page_url}",
        )
        if sent:
            runtime.link_warning_state.mark_warned(page.page_id)


async def link_warning_loop() -> None:
    await client.wait_until_ready()

    async def job():
        print("Scrapboxのリンク数を確認します", flush=True)
        await run_link_warning_check()

    async def on_error(error):
        print(f"リンク数確認処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            runtime.config.alert_channel_id,
            f"{runtime.config.mention_target}\n"
            f"ああ、もう！Scrapboxのリンク数を確認できませんでしたよ！\n"
            f"私の処理は完璧だったはずなのに...仕方ありません。エラーログの確認が必要ですね。\n"
            f"<エラーログ>\n{error}",
        )

    await run_interval_loop(
        is_closed=client.is_closed,
        interval_seconds=runtime.config.link_warning_interval_minutes * 60,
        job=job,
        on_error=on_error,
    )


@client.event
async def on_ready() -> None:
    global daily_task_started

    print("ログインしました", flush=True)

    if runtime.http_session is None or runtime.http_session.closed:
        runtime.http_session = aiohttp.ClientSession()
        runtime.diary_client.session = runtime.http_session

    if not daily_task_started:
        daily_task_started = True
        client.loop.create_task(create_page_loop())
        client.loop.create_task(check_page_loop())
        client.loop.create_task(tactical_challenge_loop())
        if runtime.config.link_warning_enabled:
            client.loop.create_task(link_warning_loop())


@client.event
async def on_disconnect() -> None:
    if runtime.http_session is not None and not runtime.http_session.closed:
        await runtime.http_session.close()
    stop_web_server()

def main() -> None:
    initialize_runtime()
    validate_env()
    register_tactical_challenge_api()
    start_web_server()
    client.run(runtime.config.token)


if __name__ == "__main__":
    main()
