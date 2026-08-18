import argparse
import asyncio
import os

from link_warning import LinkWarningState, ScrapboxLinkClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrapboxのリンク警告をDiscordへ送らず手元で確認します。"
    )
    parser.add_argument(
        "--project",
        default=os.getenv("COSENSE_PROJECT"),
        help="Scrapboxプロジェクト名（省略時: COSENSE_PROJECT）",
    )
    parser.add_argument(
        "--sid",
        default=os.getenv("COSENSE_SID", ""),
        help="connect.sidの値（省略時: COSENSE_SID）",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=int(os.getenv("LINK_WARNING_THRESHOLD", "30")),
        help="警告閾値（デフォルト: 30）",
    )
    parser.add_argument(
        "--resolve-threshold",
        type=int,
        default=None,
        help="警告解除閾値（省略時: 警告閾値より1小さい値）",
    )
    parser.add_argument(
        "--config-page",
        default=os.getenv("LINK_WARNING_CONFIG_PAGE", ""),
        help="除外設定ページ名（省略可）",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="終了せず繰り返し確認する",
    )
    parser.add_argument(
        "--interval-seconds",
        type=int,
        default=60,
        help="--watch時の確認間隔（デフォルト: 60秒）",
    )
    args = parser.parse_args()

    if not args.project:
        parser.error("--project または COSENSE_PROJECT が必要です")
    if args.interval_seconds <= 0:
        parser.error("--interval-seconds は1以上で指定してください")

    if args.resolve_threshold is None:
        configured_resolve = os.getenv("LINK_WARNING_RESOLVE_THRESHOLD")
        if configured_resolve is None:
            args.resolve_threshold = max(0, args.threshold - 1)
        else:
            try:
                args.resolve_threshold = int(configured_resolve)
            except ValueError:
                parser.error("LINK_WARNING_RESOLVE_THRESHOLD は整数で指定してください")

    if args.threshold <= 0:
        parser.error("--threshold は1以上で指定してください")
    if not 0 <= args.resolve_threshold < args.threshold:
        parser.error("解除閾値は0以上かつ警告閾値未満にしてください")

    return args


def normalize_sid(sid: str) -> str:
    sid = sid.strip()
    if sid.startswith("connect.sid="):
        return sid.removeprefix("connect.sid=").strip()
    return sid


async def run(args: argparse.Namespace) -> None:
    client = ScrapboxLinkClient(args.project, normalize_sid(args.sid))
    state = LinkWarningState(args.threshold, args.resolve_threshold)

    # 手動確認では、初回から現在の警告候補を表示する。
    state.initialized = True

    while True:
        pages = await client.fetch_page_summaries()
        exclusions = await client.fetch_excluded_titles(args.config_page)
        candidates = state.find_new_warnings(pages, exclusions)

        print(
            f"取得ページ数: {len(pages)} / 除外リンク数: {len(exclusions)}",
            flush=True,
        )

        if candidates:
            for page in sorted(
                candidates,
                key=lambda item: item.linked_count,
                reverse=True,
            ):
                print(
                    f"警告候補: [{page.title}] {page.linked_count}ページから参照",
                    flush=True,
                )
                state.mark_warned(page.page_id)
        else:
            print("新しい警告候補はありません", flush=True)

        if not args.watch:
            return

        await asyncio.sleep(args.interval_seconds)


def main() -> None:
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
