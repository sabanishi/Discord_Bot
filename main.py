from datetime import datetime
from urllib.parse import quote

import discord
from config import load_config
from diary import DiaryClient, build_page_from_template, normalize_lines
from notifications import DiscordNotifier
from scheduling import run_daily_loop, run_interval_loop
from web_server import register_tactical_challenge_api, start_web_server
from link_warning import LinkWarningState, ScrapboxLinkClient
from tactical_challenge.scheduler import (
    format_tactical_challenge_completion,
    format_tactical_challenge_error,
    run_tactical_challenge_once,
)

client = discord.Client(intents=discord.Intents.default())
notifier = DiscordNotifier(client)


TOKEN = None
DEFAULT_CHANNEL_ID = None
ALERT_CHANNEL_ID = None
COSENSE_PROJECT = None
COSENSE_SID = None
MENTION_TARGET = ""

daily_task_started = False


CREATE_PAGE_HOUR = None
CREATE_PAGE_MINUTE = None
CHECK_PAGE_HOUR = None
CHECK_PAGE_MINUTE = None
LINK_WARNING_ENABLED = False
LINK_WARNING_INTERVAL_MINUTES = None
LINK_WARNING_CONFIG_PAGE = ""
link_warning_state = None
diary_client = None


def initialize_runtime() -> None:
    """環境変数を読み込み、Bot起動に必要な実行時状態を初期化する。"""
    global TOKEN, DEFAULT_CHANNEL_ID, ALERT_CHANNEL_ID
    global COSENSE_PROJECT, COSENSE_SID, MENTION_TARGET
    global CREATE_PAGE_HOUR, CREATE_PAGE_MINUTE
    global CHECK_PAGE_HOUR, CHECK_PAGE_MINUTE
    global LINK_WARNING_ENABLED, LINK_WARNING_INTERVAL_MINUTES
    global LINK_WARNING_CONFIG_PAGE, link_warning_state, diary_client

    config = load_config()
    TOKEN = config.token
    DEFAULT_CHANNEL_ID = config.default_channel_id
    ALERT_CHANNEL_ID = config.alert_channel_id
    COSENSE_PROJECT = config.cosense_project
    COSENSE_SID = config.cosense_sid
    MENTION_TARGET = config.mention_target
    CREATE_PAGE_HOUR, CREATE_PAGE_MINUTE = config.create_page_time
    CHECK_PAGE_HOUR, CHECK_PAGE_MINUTE = config.check_page_time
    LINK_WARNING_ENABLED = config.link_warning_enabled
    LINK_WARNING_INTERVAL_MINUTES = config.link_warning_interval_minutes
    LINK_WARNING_CONFIG_PAGE = config.link_warning_config_page

    link_warning_state = LinkWarningState(
        warning_threshold=config.link_warning_threshold,
        resolve_threshold=config.link_warning_resolve_threshold,
    )
    diary_client = DiaryClient(COSENSE_PROJECT, COSENSE_SID)


def normalize_sid(sid: str) -> str:
    sid = sid.strip()

    if sid.startswith("connect.sid="):
        return sid.removeprefix("connect.sid=").strip()

    return sid


def get_encoded_project() -> str:
    return quote(COSENSE_PROJECT, safe="")


def validate_env():
    if not TOKEN:
        raise RuntimeError("環境変数 DISCORD_TOKEN が設定されていません")

    if not DEFAULT_CHANNEL_ID:
        raise RuntimeError("環境変数 DISCORD_DEFAULT_CHANNEL_ID が設定されていません")

    if not ALERT_CHANNEL_ID:
        raise RuntimeError("環境変数 DISCORD_ALERT_CHANNEL_ID が設定されていません")

    if not COSENSE_PROJECT:
        raise RuntimeError("環境変数 COSENSE_PROJECT が設定されていません")

    if not COSENSE_SID:
        raise RuntimeError("環境変数 COSENSE_SID が設定されていません")


def get_page_url(title: str) -> str:
    encoded_project = get_encoded_project()
    encoded_title = quote(title, safe="")

    return f"https://scrapbox.io/{encoded_project}/{encoded_title}"


async def run_create_job(target: datetime):
    title, lines = build_page_from_template(target)
    page_url = await diary_client.create_page(title, lines)

    await notifier.send(
        DEFAULT_CHANNEL_ID,
        f"おはようございます。今日の日記ページはこちらです。\n{page_url}",
    )


async def run_check_job(target: datetime):
    title, expected_lines = build_page_from_template(target)
    actual_lines = await diary_client.fetch_page_lines(title)

    expected = normalize_lines(expected_lines)
    actual = normalize_lines(actual_lines)

    page_url = get_page_url(title)

    if actual == expected:
        await notifier.send(
            ALERT_CHANNEL_ID,
            f"{MENTION_TARGET}\n"
            f"もう、何やってたんですか！　まだ日記が更新されていませんよ！\n"
            f"早く済ませてください。\n"
            f"{page_url}",
        )


async def create_page_loop():
    async def job(target):
        print(f"Scrapboxページを作成します: {target}", flush=True)
        await run_create_job(target)

    async def on_error(error):
        print(f"ページ作成処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            ALERT_CHANNEL_ID,
            f"{MENTION_TARGET}\nScrapboxページが作成できませんでしたよ。\n"
            f"何かバグがあるんじゃないですか？:\n<エラーログ>\n{error}",
        )

    await run_daily_loop(
        client=client,
        hour=CREATE_PAGE_HOUR,
        minute=CREATE_PAGE_MINUTE,
        job=job,
        on_error=on_error,
    )


async def check_page_loop():
    async def job(target):
        print(f"Scrapboxページの変更を確認します:\n{target}", flush=True)
        await run_check_job(target)

    async def on_error(error):
        print(f"ページ確認処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            ALERT_CHANNEL_ID,
            f"{MENTION_TARGET}\nああ、もう！日記がチェックできませんでしたよ！\n"
            f"ちゃんとプログラム書いてください！:\n<エラーログ>\n{error}",
        )

    await run_daily_loop(
        client=client,
        hour=CHECK_PAGE_HOUR,
        minute=CHECK_PAGE_MINUTE,
        job=job,
        on_error=on_error,
    )


async def tactical_challenge_loop():
    """毎日21:15に戦術対抗戦ページをリファクタする。"""
    async def job(target):
        print(f"戦術対抗戦ページを更新します: {target}", flush=True)
        results = await run_tactical_challenge_once()
        await notifier.send(
            DEFAULT_CHANNEL_ID,
            format_tactical_challenge_completion(results),
        )

    async def on_error(error):
        print(f"戦術対抗戦ページ更新処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            ALERT_CHANNEL_ID,
            f"{MENTION_TARGET}\n{format_tactical_challenge_error(error)}",
        )

    await run_daily_loop(
        client=client,
        hour=CHECK_PAGE_HOUR,
        minute=CHECK_PAGE_MINUTE,
        job=job,
        on_error=on_error,
    )


async def run_link_warning_check():
    cosense = ScrapboxLinkClient(
        project=COSENSE_PROJECT,
        sid=normalize_sid(COSENSE_SID),
    )
    pages = await cosense.fetch_page_summaries()
    excluded_titles = await cosense.fetch_excluded_titles(LINK_WARNING_CONFIG_PAGE)
    candidates = link_warning_state.find_new_warnings(pages, excluded_titles)

    for page in candidates:
        page_url = get_page_url(page.title)
        sent = await notifier.send(
            ALERT_CHANNEL_ID,
            f"{MENTION_TARGET}\n"
            f"「{page.title}」が{page.linked_count}個のページから参照されているようですね。\n"
            f"そろそろ整理や分割を考えた方が良いんじゃないですか？\n"
            f"{page_url}",
        )
        if sent:
            link_warning_state.mark_warned(page.page_id)


async def link_warning_loop():
    await client.wait_until_ready()

    async def job():
        print("Scrapboxのリンク数を確認します", flush=True)
        await run_link_warning_check()

    async def on_error(error):
        print(f"リンク数確認処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            ALERT_CHANNEL_ID,
            f"{MENTION_TARGET}\n"
            f"ああ、もう！Scrapboxのリンク数を確認できませんでしたよ！\n"
            f"私の処理は完璧だったはずなのに...仕方ありません。エラーログの確認が必要ですね。\n"
            f"<エラーログ>\n{error}",
        )

    await run_interval_loop(
        is_closed=client.is_closed,
        interval_seconds=LINK_WARNING_INTERVAL_MINUTES * 60,
        job=job,
        on_error=on_error,
    )


@client.event
async def on_ready():
    global daily_task_started

    print("ログインしました", flush=True)

    if not daily_task_started:
        daily_task_started = True
        client.loop.create_task(create_page_loop())
        client.loop.create_task(check_page_loop())
        client.loop.create_task(tactical_challenge_loop())
        if LINK_WARNING_ENABLED:
            client.loop.create_task(link_warning_loop())

def main() -> None:
    initialize_runtime()
    validate_env()
    register_tactical_challenge_api()
    start_web_server()
    client.run(TOKEN)


if __name__ == "__main__":
    main()
