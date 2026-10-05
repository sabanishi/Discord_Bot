import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tools.run_mirroring import preview_once, run_once


class RunMirroringToolTests(unittest.TestCase):
    def test_run_once_executes_mirroring_without_discord_settings(self):
        result = SimpleNamespace(
            imported_pages=2,
            created_pages=1,
            updated_pages=1,
            deleted_pages=0,
            excluded_pages=3,
            failed_pages=0,
        )
        service = SimpleNamespace(run=AsyncMock(return_value=result))

        class SessionContext:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, exc_type, exc, traceback):
                return None

        environ = {
            "COSENSE_PROJECT": "private-project",
            "COSENSE_SID": "connect.sid=session",
            "MIRROR_PUBLIC_PROJECT": "public-project",
            "MIRROR_EXCLUSION_CONFIG_PAGE": "除外設定",
            "MIRROR_REPLACEMENT_CONFIG_PAGE": "置換設定",
        }
        with patch("tools.run_mirroring.aiohttp.ClientSession", return_value=SessionContext()), patch(
            "tools.run_mirroring.MirrorService", return_value=service
        ) as service_class:
            actual = asyncio.run(run_once(environ))

        self.assertIs(actual, result)
        service_class.assert_called_once()
        service.run.assert_awaited_once_with()

    def test_run_once_rejects_missing_mirroring_settings(self):
        with self.assertRaisesRegex(RuntimeError, "MIRROR_PUBLIC_PROJECT"):
            asyncio.run(run_once({"COSENSE_PROJECT": "private", "COSENSE_SID": "sid"}))

    def test_preview_once_uses_preview_without_running_mirroring(self):
        preview = SimpleNamespace(
            replacement_rules={"個人情報": "公開用表現"},
            included_titles=[("原本ページ", "公開ページ")],
            excluded_titles=["除外ページ"],
            failed_titles=[],
        )
        service = SimpleNamespace(
            preview=AsyncMock(return_value=preview),
            run=AsyncMock(),
        )

        class SessionContext:
            async def __aenter__(self):
                return object()

            async def __aexit__(self, exc_type, exc, traceback):
                return None

        environ = {
            "COSENSE_PROJECT": "private-project",
            "COSENSE_SID": "connect.sid=session",
            "MIRROR_PUBLIC_PROJECT": "public-project",
            "MIRROR_EXCLUSION_CONFIG_PAGE": "除外設定",
            "MIRROR_REPLACEMENT_CONFIG_PAGE": "置換設定",
        }
        with patch("tools.run_mirroring.aiohttp.ClientSession", return_value=SessionContext()), patch(
            "tools.run_mirroring.MirrorService", return_value=service
        ):
            actual = asyncio.run(preview_once(environ))

        self.assertIs(actual, preview)
        service.preview.assert_awaited_once_with()
        service.run.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
