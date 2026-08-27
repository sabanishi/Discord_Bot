import os
import unittest
from unittest.mock import AsyncMock, patch

from tactical_challenge.scheduler import (
    format_tactical_challenge_completion,
    format_tactical_challenge_error,
    run_tactical_challenge_once,
)
from tactical_challenge import TargetPageResult


class TacticalChallengeSchedulerTest(unittest.IsolatedAsyncioTestCase):
    def test_formats_completion_summary(self):
        message = format_tactical_challenge_completion(
            [
                TargetPageResult("ページA", 3, ("イオリ(水着)",)),
                TargetPageResult("ページB", 0, ()),
            ]
        )

        self.assertEqual(
            message,
            "戦術対抗戦ページの更新処理は、無事に完了しました。\n"
            "対象ページ: 2件\n"
            "更新ページ: 1件\n"
            "変更行: 3行\n"
            "新規アイコン: 1件\n"
            "ふふん、当然の結果です。",
        )

    def test_formats_error_report(self):
        self.assertEqual(
            format_tactical_challenge_error("接続に失敗しました"),
            "……おかしいですね。戦術対抗戦ページの更新処理でエラーを検知しました。\n"
            "<エラーログ>\n"
            "接続に失敗しました\n"
            "想定外です。原因を精査する必要があります。",
        )

    async def test_runs_refactor_with_configured_clients(self):
        with patch.dict(
            os.environ,
            {
                "COSENSE_PROJECT": "project",
                "COSENSE_SID": "sid",
                "GYAZO_ACCESS_TOKEN": "token",
            },
            clear=False,
        ), patch("tactical_challenge.scheduler.BlueArchiveWikiClient") as wiki, patch(
            "tactical_challenge.scheduler.GyazoClient"
        ) as gyazo, patch(
            "tactical_challenge.scheduler.TacticalChallengeCosenseClient"
        ) as cosense, patch(
            "tactical_challenge.scheduler.refactor_target_pages",
            new_callable=AsyncMock,
        ) as refactor:
            refactor.return_value = []

            result = await run_tactical_challenge_once()

        self.assertEqual(result, [])
        wiki.assert_called_once_with()
        gyazo.assert_called_once_with("token")
        cosense.assert_called_once_with(project="project", sid="sid")
        refactor.assert_awaited_once_with(
            wiki.return_value,
            gyazo.return_value,
            cosense.return_value,
        )


if __name__ == "__main__":
    unittest.main()
