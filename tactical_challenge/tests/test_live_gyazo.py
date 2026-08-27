import os
from pathlib import Path
import unittest

import aiohttp

from tactical_challenge import BlueArchiveWikiClient, GyazoClient
from tactical_challenge.tests.env_loader import load_test_env
from tactical_challenge.tests.image_assertions import assert_image_bytes


load_test_env(Path(__file__).parents[2] / ".env")


class LiveGyazoTest(unittest.IsolatedAsyncioTestCase):
    async def test_uploads_wiki_icon_image(self):
        """攻略Wikiのアイコン画像を実際のGyazo APIへアップロードする。"""
        access_token = os.getenv("GYAZO_ACCESS_TOKEN")
        self.assertTrue(
            access_token,
            "Gyazo実APIテストにはGYAZO_ACCESS_TOKENが必要です",
        )

        wiki = BlueArchiveWikiClient()
        icons = await wiki.fetch_student_icons()
        sample = next(icon for icon in icons if icon.name == "イオリ(水着)")
        image = await wiki.fetch_icon_image(sample.image_url)

        gyazo = GyazoClient(access_token)
        uploaded = await gyazo.upload_image(
            image,
            filename="イオリ(水着).png",
        )

        self.assertTrue(uploaded.image_id)
        self.assertTrue(uploaded.permalink_url.startswith("https://gyazo.com/"))
        self.assertTrue(uploaded.image_url.startswith("https://i.gyazo.com/"))
        async with aiohttp.ClientSession() as session:
            async with session.get(uploaded.image_url) as response:
                downloaded = await response.read()
                self.assertEqual(response.status, 200)
                self.assertTrue(
                    response.headers.get("Content-Type", "").startswith("image/"),
                )
        assert_image_bytes(self, downloaded)
        self.assertEqual(downloaded, image)


if __name__ == "__main__":
    unittest.main()
