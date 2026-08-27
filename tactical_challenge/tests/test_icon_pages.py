import json
import unittest
from unittest.mock import patch

from tactical_challenge import (
    IconPageError,
    build_icon_page_import_data,
    build_icon_page_title,
    is_ready_icon_page,
    is_persistent_cosense_page,
    TacticalChallengeCosenseClient,
)


class IconPageTest(unittest.TestCase):
    def test_builds_icon_page_title_from_canonical_student_name(self):
        self.assertEqual(
            build_icon_page_title("イオリ(水着)"),
            "!イオリ(水着)",
        )


class _FakeResponse:
    def __init__(self, status: int, body: str):
        self.status = status
        self.body = body

    async def text(self):
        return self.body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _FakeSession:
    def __init__(self):
        self.get_calls = []
        self.post_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return _FakeResponse(200, json.dumps({"persistent": False}))

    def post(self, url, **kwargs):
        self.post_calls.append((url, kwargs))
        return _FakeResponse(200, '{"message":"import success! - 1 pages"}')


class IconPageWriteTest(unittest.IsolatedAsyncioTestCase):
    async def test_posts_import_when_icon_page_is_not_persistent(self):
        session = _FakeSession()
        client = TacticalChallengeCosenseClient("project name", "sid-value")

        with patch(
            "tactical_challenge.cosense_client.aiohttp.ClientSession",
            return_value=session,
        ):
            created = await client.ensure_icon_page(
                "イオリ(水着)",
                "https://i.gyazo.com/0123456789abcdef.png",
            )

        self.assertTrue(created)
        self.assertEqual(len(session.get_calls), 1)
        self.assertEqual(len(session.post_calls), 1)
        post_url, post_options = session.post_calls[0]
        self.assertEqual(
            post_url,
            "https://scrapbox.io/api/page-data/import/project%20name.json",
        )
        self.assertEqual(
            post_options["headers"]["Cookie"],
            "connect.sid=sid-value",
        )
        self.assertNotIn("X-CSRF-TOKEN", post_options["headers"])
        self.assertIn("data", post_options)

    def test_builds_page_data_with_gyazo_image_url(self):
        page_data = build_icon_page_import_data(
            "イオリ(水着)",
            "https://i.gyazo.com/0123456789abcdef.png",
        )

        self.assertEqual(
            page_data,
            {
                "pages": [
                    {
                        "title": "!イオリ(水着)",
                        "created": 1,
                        "lines": [
                            {"text": "!イオリ(水着)", "created": 1},
                            {
                                "text": (
                                    "[https://i.gyazo.com/"
                                    "0123456789abcdef.png]"
                                ),
                                "created": 1,
                            },
                            {
                                "text": " This page was auto generated.",
                                "created": 1,
                            },
                            {
                                "text": "#戦術対抗戦_アイコン",
                                "created": 1,
                            },
                        ],
                    }
                ]
            },
        )

    def test_rejects_non_gyazo_image_url(self):
        with self.assertRaisesRegex(IconPageError, "Gyazo"):
            build_icon_page_import_data(
                "イオリ(水着)",
                "https://example.com/iori.png",
            )

    def test_treats_persistent_page_as_existing(self):
        self.assertTrue(is_persistent_cosense_page({"persistent": True}))

    def test_treats_non_persistent_page_as_missing(self):
        self.assertFalse(is_persistent_cosense_page({"persistent": False}))

    def test_treats_page_with_gyazo_title_image_as_ready(self):
        self.assertTrue(
            is_ready_icon_page(
                {
                    "persistent": True,
                    "created": 1,
                    "image": "https://i.gyazo.com/0123456789abcdef.png/raw",
                    "lines": [
                        {"text": "!イオリ(水着)"},
                        {
                            "text": (
                                "[https://i.gyazo.com/"
                                "0123456789abcdef.png]"
                            )
                        },
                        {"text": " This page was auto generated."},
                        {"text": "#戦術対抗戦_アイコン"},
                    ],
                }
            )
        )

    def test_treats_persistent_page_without_title_image_as_not_ready(self):
        self.assertFalse(
            is_ready_icon_page({"persistent": True, "image": None})
        )

    def test_treats_recently_created_icon_page_as_not_ready(self):
        self.assertFalse(
            is_ready_icon_page(
                {
                    "persistent": True,
                    "created": 1_700_000_000,
                    "image": "https://i.gyazo.com/0123456789abcdef.png/raw",
                    "lines": [
                        {"text": "!イオリ(水着)"},
                        {
                            "text": (
                                "[https://i.gyazo.com/"
                                "0123456789abcdef.png]"
                            )
                        },
                        {"text": " This page was auto generated."},
                        {"text": "#戦術対抗戦_アイコン"},
                    ],
                }
            )
        )

    def test_treats_page_without_tactical_challenge_tag_as_not_ready(self):
        self.assertFalse(
            is_ready_icon_page(
                {
                    "persistent": True,
                    "created": 1,
                    "image": "https://i.gyazo.com/0123456789abcdef.png/raw",
                    "lines": [
                        {"text": "!イオリ(水着)"},
                        {
                            "text": (
                                "[https://i.gyazo.com/"
                                "0123456789abcdef.png]"
                            )
                        },
                    ],
                }
            )
        )

    def test_treats_page_without_auto_generated_line_as_not_ready(self):
        self.assertFalse(
            is_ready_icon_page(
                {
                    "persistent": True,
                    "created": 1,
                    "image": "https://i.gyazo.com/0123456789abcdef.png/raw",
                    "lines": [
                        {"text": "!イオリ(水着)"},
                        {
                            "text": (
                                "[https://i.gyazo.com/"
                                "0123456789abcdef.png]"
                            )
                        },
                        {"text": "#戦術対抗戦_アイコン"},
                    ],
                }
            )
        )

    def test_treats_page_with_different_body_and_title_images_as_not_ready(self):
        self.assertFalse(
            is_ready_icon_page(
                {
                    "persistent": True,
                    "created": 1,
                    "image": "https://i.gyazo.com/title-image.png/raw",
                    "lines": [
                        {"text": "!イオリ(水着)"},
                        {"text": "[https://i.gyazo.com/body-image.png]"},
                        {"text": " This page was auto generated."},
                        {"text": "#戦術対抗戦_アイコン"},
                    ],
                }
            )
        )


if __name__ == "__main__":
    unittest.main()
