from urllib.parse import quote

from diary import build_page_from_template, normalize_lines


def get_page_url(state, title: str) -> str:
    project = quote(state.config.cosense_project, safe="")
    encoded_title = quote(title, safe="")
    return f"https://scrapbox.io/{project}/{encoded_title}"


async def run_create_job(state, notifier, target) -> None:
    title, lines = build_page_from_template(target)
    page_url = await state.diary_client.create_page(title, lines)
    await notifier.send(
        state.config.default_channel_id,
        f"おはようございます。今日の日記ページはこちらです。\n{page_url}",
    )


async def run_check_job(state, notifier, target) -> None:
    title, expected_lines = build_page_from_template(target)
    actual_lines = await state.diary_client.fetch_page_lines(title)
    expected = normalize_lines(expected_lines)
    actual = normalize_lines(actual_lines)
    if actual != expected:
        return

    page_url = get_page_url(state, title)
    await notifier.send(
        state.config.alert_channel_id,
        f"{state.config.mention_target}\n"
        f"もう、何やってたんですか！　まだ日記が更新されていませんよ！\n"
        f"早く済ませてください。\n{page_url}",
    )
