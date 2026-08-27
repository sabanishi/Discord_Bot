import os

from .cosense_client import TacticalChallengeCosenseClient
from .gyazo_client import GyazoClient
from .target_page_service import refactor_target_pages
from .wiki_client import BlueArchiveWikiClient


def format_tactical_challenge_completion(results) -> str:
    """戦術対抗戦の処理結果をDiscord通知文へ整形する。"""
    updated_pages = sum(result.changed_lines > 0 for result in results)
    changed_lines = sum(result.changed_lines for result in results)
    created_icons = sum(len(result.created_icons) for result in results)
    return (
        "戦術対抗戦ページの更新処理は、無事に完了しました。\n"
        f"対象ページ: {len(results)}件\n"
        f"更新ページ: {updated_pages}件\n"
        f"変更行: {changed_lines}行\n"
        f"新規アイコン: {created_icons}件\n"
        "ふふん、当然の結果です。"
    )


def format_tactical_challenge_error(error: object) -> str:
    """戦術対抗戦のエラーをケイ風の報告文へ整形する。"""
    return (
        "……おかしいですね。戦術対抗戦ページの更新処理でエラーを検知しました。\n"
        "<エラーログ>\n"
        f"{error}\n"
        "想定外です。原因を精査する必要があります。"
    )


async def run_tactical_challenge_once():
    """戦術対抗戦の対象ページを1回リファクタする。"""
    project = os.getenv("COSENSE_PROJECT", "").strip()
    sid = os.getenv("COSENSE_SID", "").strip()
    gyazo_token = os.getenv("GYAZO_ACCESS_TOKEN", "").strip()
    if not project or not sid or not gyazo_token:
        raise RuntimeError(
            "戦術対抗戦機能にはCOSENSE_PROJECT、COSENSE_SID、"
            "GYAZO_ACCESS_TOKENが必要です"
        )

    wiki = BlueArchiveWikiClient()
    gyazo = GyazoClient(gyazo_token)
    cosense = TacticalChallengeCosenseClient(project=project, sid=sid)
    return await refactor_target_pages(wiki, gyazo, cosense)
