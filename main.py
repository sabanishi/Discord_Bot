import asyncio
import json
import os
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import aiohttp
import discord
from keep_alive import keep_alive

client = discord.Client(intents=discord.Intents.default())


def build_mention_target() -> str:
    user_id = os.getenv("MENTION_TARGET", "").strip()

    if not user_id:
        return ""

    return f"<@{user_id}>"


TOKEN = os.getenv("DISCORD_TOKEN")
DEFAULT_CHANNEL_ID = int(os.getenv("DISCORD_DEFAULT_CHANNEL_ID"))
ALERT_CHANNEL_ID = int(os.getenv("DISCORD_ALERT_CHANNEL_ID"))
COSENSE_PROJECT = os.getenv("COSENSE_PROJECT")
COSENSE_SID = os.getenv("COSENSE_SID")
MENTION_TARGET = build_mention_target()

JST = ZoneInfo("Asia/Tokyo")

daily_task_started = False


def parse_time_env(env_name: str, default_value: str) -> tuple[int, int]:
    value = os.getenv(env_name, default_value)

    try:
        hour_text, minute_text = value.split(":")
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        raise RuntimeError(f"環境変数 {env_name} は HH:MM 形式で指定してください\n現在の値: {value}")

    if not 0 <= hour <= 23:
        raise RuntimeError(f"環境変数 {env_name} の時が不正です。0〜23で指定してください\n現在の値: {value}")

    if not 0 <= minute <= 59:
        raise RuntimeError(f"環境変数 {env_name} の分が不正です。0〜59で指定してください\n現在の値: {value}")

    return hour, minute


CREATE_PAGE_HOUR, CREATE_PAGE_MINUTE = parse_time_env("CREATE_PAGE_TIME", "7:00")
CHECK_PAGE_HOUR, CHECK_PAGE_MINUTE = parse_time_env("CHECK_PAGE_TIME", "21:15")


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


def build_page_from_template(target_date: datetime) -> tuple[str, list[str]]:
    today = target_date.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    with open("template.txt", "r", encoding="utf-8") as f:
        template = f.read()

    text = (
        template
        .replace("${year}", today.strftime("%Y"))
        .replace("${month}", today.strftime("%m"))
        .replace("${today}", today.strftime("%Y-%m-%d"))
        .replace("${yesterday}", yesterday.strftime("%Y-%m-%d"))
        .replace("${tomorrow}", tomorrow.strftime("%Y-%m-%d"))
    )

    lines = text.splitlines()

    if not lines or not lines[0].strip():
        raise ValueError("template.txt の1行目にはページタイトルになる ${today} が必要です")

    title = lines[0]
    return title, lines


def get_cosense_read_headers() -> dict[str, str]:
    sid = normalize_sid(COSENSE_SID)

    return {
        "Accept": "application/json, text/plain, */*",
        "Cookie": f"connect.sid={sid}",
    }


def get_cosense_import_headers() -> dict[str, str]:
    sid = normalize_sid(COSENSE_SID)
    encoded_project = get_encoded_project()

    return {
        "Accept": "application/json, text/plain, */*",
        "Cookie": f"connect.sid={sid}",
        "Origin": "https://scrapbox.io",
        "Referer": f"https://scrapbox.io/{encoded_project}/settings/page-data",
    }


def get_page_url(title: str) -> str:
    encoded_project = get_encoded_project()
    encoded_title = quote(title, safe="")

    return f"https://scrapbox.io/{encoded_project}/{encoded_title}"


async def safe_send(channel_id: int, message: str) -> bool:
    channel = client.get_channel(channel_id)

    if channel is None:
        print(f"チャンネルが見つかりません:\n{channel_id}", flush=True)
        return False

    if len(message) > 1800:
        message = f"{message[:1800]}\n...(長すぎるため省略しました)"

    try:
        await channel.send(message)
        return True
    except discord.HTTPException as e:
        print(f"Discordへのメッセージ送信に失敗しました:\n{e}", flush=True)
        return False
    except Exception as e:
        print(f"Discordへのメッセージ送信で予期しないエラーが発生しました:\n{e}", flush=True)
        return False


def build_import_form(import_data: dict) -> aiohttp.FormData:
    form = aiohttp.FormData()

    form.add_field(
        "import-file",
        json.dumps(import_data, ensure_ascii=False).encode("utf-8"),
        filename="import.json",
        content_type="application/octet-stream",
    )

    return form


async def create_cosense_page(title: str, lines: list[str]) -> str:
    validate_env()

    encoded_project = get_encoded_project()
    url = f"https://scrapbox.io/api/page-data/import/{encoded_project}.json"

    import_data = {
        "pages": [
            {
                "title": title,
                "lines": lines,
            }
        ]
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            headers=get_cosense_import_headers(),
            data=build_import_form(import_data),
        ) as response:
            response_text = await response.text()

            if response.status < 200 or response.status >= 300:
                raise RuntimeError(
                    f"Scrapboxページ作成に失敗しました:\n"
                    f"status={response.status}, body={response_text}"
                )

    return get_page_url(title)


async def fetch_cosense_page_lines(title: str) -> list[str]:
    validate_env()

    encoded_project = get_encoded_project()
    encoded_title = quote(title, safe="")
    url = f"https://scrapbox.io/api/pages/{encoded_project}/{encoded_title}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=get_cosense_read_headers()) as response:
            response_text = await response.text()

            if response.status == 404:
                raise RuntimeError(f"Scrapboxページが見つかりません:\n{title}")

            if response.status < 200 or response.status >= 300:
                raise RuntimeError(
                    f"Scrapboxページ取得に失敗しました:\n"
                    f"status={response.status}, body={response_text}"
                )

            data = json.loads(response_text)

    if "lines" not in data:
        raise RuntimeError(
            f"Scrapboxページ取得結果が不正です:\n"
            f"title:\n{title}\n"
            f"response_text:\n{response_text}"
        )

    return [line.get("text", "") for line in data["lines"]]


async def run_create_job(target: datetime):
    title, lines = build_page_from_template(target)
    page_url = await create_cosense_page(title, lines)

    await safe_send(
        DEFAULT_CHANNEL_ID,
        f"おはようございます。今日の日記ページはこちらです。\n{page_url}",
    )


def normalize_lines(lines: list[str]) -> list[str]:
    """
    比較用に末尾の空行だけ無視する
    途中の空行や本文の空白は変更として扱う
    """
    normalized = list(lines)

    while normalized and normalized[-1] == "":
        normalized.pop()

    return normalized


async def run_check_job(target: datetime):
    title, expected_lines = build_page_from_template(target)
    actual_lines = await fetch_cosense_page_lines(title)

    expected = normalize_lines(expected_lines)
    actual = normalize_lines(actual_lines)

    page_url = get_page_url(title)

    if actual == expected:
        await safe_send(
            ALERT_CHANNEL_ID,
            f"{MENTION_TARGET}\n"
            f"もう、何やってたんですか！　まだ日記が更新されていませんよ！\n"
            f"早く済ませてください。\n"
            f"{page_url}",
        )


async def sleep_until_next_time(hour: int, minute: int) -> datetime:
    now = datetime.now(JST)

    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    if now >= target:
        target += timedelta(days=1)

    wait_seconds = (target - now).total_seconds()
    await asyncio.sleep(wait_seconds)

    return target


async def create_page_loop():
    await client.wait_until_ready()

    while not client.is_closed():
        target = await sleep_until_next_time(
            hour=CREATE_PAGE_HOUR,
            minute=CREATE_PAGE_MINUTE,
        )

        try:
            print(f"Cosenseページを作成します: {target}", flush=True)
            await run_create_job(target)
        except Exception as e:
            print(f"ページ作成処理でエラーが発生しました:\n{e}", flush=True)

            await safe_send(
                ALERT_CHANNEL_ID,
                f"{MENTION_TARGET}\n"
                f"Scrapboxページが作成できませんでしたよ。\n"
                f"何かバグがあるんじゃないですか？:\n"
                f"<エラーログ>\n"
                f"{e}",
            )


async def check_page_loop():
    await client.wait_until_ready()

    while not client.is_closed():
        target = await sleep_until_next_time(
            hour=CHECK_PAGE_HOUR,
            minute=CHECK_PAGE_MINUTE,
        )

        try:
            print(f"Cosenseページの変更を確認します:\n{target}", flush=True)
            await run_check_job(target)
        except Exception as e:
            print(f"ページ確認処理でエラーが発生しました:\n{e}", flush=True)

            await safe_send(
                ALERT_CHANNEL_ID,
                f"{MENTION_TARGET}\n"
                f"ああ、もう！日記がチェックできませんでしたよ！\n"
                f"ちゃんとプログラム書いてください！:\n"
                f"<エラーログ>\n"
                f"{e}",
            )


@client.event
async def on_ready():
    global daily_task_started

    print("ログインしました", flush=True)

    if not daily_task_started:
        daily_task_started = True
        client.loop.create_task(create_page_loop())
        client.loop.create_task(check_page_loop())


keep_alive()
client.run(TOKEN)