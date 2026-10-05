from datetime import datetime

import discord

from app.jobs import get_page_url, run_check_job, run_create_job
from app.config import normalize_sid
from app.link_warning import ScrapboxLinkClient
from app.scheduling import run_daily_loop, run_interval_loop
from app.tactical_challenge.scheduler import (
    format_tactical_challenge_completion,
    format_tactical_challenge_error,
    run_tactical_challenge_once,
)
from app.notifications import DiscordNotifier
from app.runtime import RuntimeState


def register_scheduled_tasks(client: discord.Client, state: RuntimeState, notifier: DiscordNotifier) -> bool:
    if getattr(state, "tasks_started", False):
        return False

    state.tasks_started = True
    client.loop.create_task(create_page_loop(client, state, notifier))
    client.loop.create_task(check_page_loop(client, state, notifier))
    client.loop.create_task(tactical_challenge_loop(client, state, notifier))
    if getattr(state, "mirror_service", None) is not None:
        for hour in state.config.mirror_run_hours:
            client.loop.create_task(mirror_loop(client, state, notifier, hour))
    if state.config.link_warning_enabled:
        client.loop.create_task(link_warning_loop(client, state, notifier))
    return True


async def create_page_loop(client: discord.Client, state: RuntimeState, notifier: DiscordNotifier) -> None:
    async def job(target: datetime) -> None:
        print(f"Scrapboxページを作成します: {target}", flush=True)
        await run_create_job(state, notifier, target)

    async def on_error(error: Exception):
        print(f"ページ作成処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            state.config.alert_channel_id,
            f"{state.config.mention_target}\nScrapboxページが作成できませんでしたよ。\n"
            f"何かバグがあるんじゃないですか？:\n<エラーログ>\n{error}",
        )

    await run_daily_loop(
        wait_until_ready=client.wait_until_ready,
        is_closed=client.is_closed,
        hour=state.config.create_page_time[0],
        minute=state.config.create_page_time[1],
        job=job,
        on_error=on_error,
    )


async def check_page_loop(client: discord.Client, state: RuntimeState, notifier: DiscordNotifier) -> None:
    async def job(target: datetime) -> None:
        print(f"Scrapboxページの変更を確認します:\n{target}", flush=True)
        await run_check_job(state, notifier, target)

    async def on_error(error: Exception):
        print(f"ページ確認処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            state.config.alert_channel_id,
            f"{state.config.mention_target}\nああ、もう！日記がチェックできませんでしたよ！\n"
            f"ちゃんとプログラム書いてください！:\n<エラーログ>\n{error}",
        )

    await run_daily_loop(
        wait_until_ready=client.wait_until_ready,
        is_closed=client.is_closed,
        hour=state.config.check_page_time[0],
        minute=state.config.check_page_time[1],
        job=job,
        on_error=on_error,
    )


async def tactical_challenge_loop(client: discord.Client, state: RuntimeState, notifier: DiscordNotifier) -> None:
    async def job(target: datetime) -> None:
        print(f"戦術対抗戦ページを更新します: {target}", flush=True)
        results = await run_tactical_challenge_once()
        await notifier.send(
            state.config.default_channel_id,
            format_tactical_challenge_completion(results),
        )

    async def on_error(error: Exception):
        print(f"戦術対抗戦ページ更新処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            state.config.alert_channel_id,
            f"{state.config.mention_target}\n{format_tactical_challenge_error(error)}",
        )

    await run_daily_loop(
        wait_until_ready=client.wait_until_ready,
        is_closed=client.is_closed,
        hour=state.config.check_page_time[0],
        minute=state.config.check_page_time[1],
        job=job,
        on_error=on_error,
    )


async def mirror_loop(
    client: discord.Client,
    state: RuntimeState,
    notifier: DiscordNotifier,
    hour: int,
) -> None:
    async def job(target: datetime) -> None:
        print(f"Scrapboxページをミラーリングします: {target}", flush=True)
        await state.mirror_service.run()

    async def on_error(error: Exception):
        print(f"Scrapboxミラーリング処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            state.config.alert_channel_id,
            f"{state.config.mention_target}\n"
            f"Scrapboxのミラーリングに失敗しました。\n"
            f"<エラーログ>\n{error}",
        )

    await run_daily_loop(
        wait_until_ready=client.wait_until_ready,
        is_closed=client.is_closed,
        hour=hour,
        minute=0,
        job=job,
        on_error=on_error,
    )


async def link_warning_loop(client: discord.Client, state: RuntimeState, notifier: DiscordNotifier) -> None:
    await client.wait_until_ready()

    async def job() -> None:
        print("Scrapboxのリンク数を確認します", flush=True)
        await run_link_warning_check(state, notifier)

    async def on_error(error: Exception):
        print(f"リンク数確認処理でエラーが発生しました:\n{error}", flush=True)
        await notifier.send(
            state.config.alert_channel_id,
            f"{state.config.mention_target}\n"
            f"ああ、もう！Scrapboxのリンク数を確認できませんでしたよ！\n"
            f"私の処理は完璧だったはずなのに...仕方ありません。エラーログの確認が必要ですね。\n"
            f"<エラーログ>\n{error}",
        )

    await run_interval_loop(
        is_closed=client.is_closed,
        interval_seconds=state.config.link_warning_interval_minutes * 60,
        job=job,
        on_error=on_error,
    )


async def run_link_warning_check(state: RuntimeState, notifier: DiscordNotifier) -> None:
        cosense = ScrapboxLinkClient(
            project=state.config.cosense_project,
            sid=normalize_sid(state.config.cosense_sid),
            session=state.http_session,
        )
        pages = await cosense.fetch_page_summaries()
        excluded_titles = await cosense.fetch_excluded_titles(state.config.link_warning_config_page)
        candidates = state.link_warning_state.find_new_warnings(pages, excluded_titles)
        for page in candidates:
            sent = await notifier.send(
                state.config.alert_channel_id,
                f"{state.config.mention_target}\n"
                f"「{page.title}」が{page.linked_count}個のページから参照されているようですね。\n"
                f"そろそろ整理や分割を考えた方が良いんじゃないですか？\n"
                f"{get_page_url(state, page.title)}",
            )
            if sent:
                state.link_warning_state.mark_warned(page.page_id)
