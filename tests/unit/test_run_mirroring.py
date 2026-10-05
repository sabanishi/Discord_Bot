import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tools.run_mirroring import run_once


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


if __name__ == "__main__":
    unittest.main()
