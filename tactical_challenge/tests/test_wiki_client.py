import unittest

from tactical_challenge import BlueArchiveWikiClient


class BlueArchiveWikiClientTest(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_lookalike_external_image_host(self):
        client = BlueArchiveWikiClient()

        with self.assertRaisesRegex(ValueError, "攻略Wiki以外"):
            await client.fetch_icon_image(
                "https://bluearchive.wikiru.jp.example.com/icon.png"
            )


if __name__ == "__main__":
    unittest.main()
