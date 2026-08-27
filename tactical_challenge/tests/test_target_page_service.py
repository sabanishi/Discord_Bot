import unittest
from types import SimpleNamespace

from tactical_challenge import (
    StudentIcon,
    TargetPageResult,
    refactor_target_pages,
)


class _WikiClient:
    def __init__(self):
        self.images = []

    async def fetch_student_icons(self):
        return [
            StudentIcon("エイミ", "https://bluearchive.wikiru.jp/eimi.png"),
            StudentIcon(
                "イオリ(水着)",
                "https://bluearchive.wikiru.jp/iori.png",
            ),
        ]

    async def fetch_icon_image(self, image_url):
        self.images.append(image_url)
        return b"image-bytes"


class _GyazoClient:
    def __init__(self):
        self.uploads = []

    async def upload_image(self, image, filename):
        self.uploads.append((image, filename))
        return SimpleNamespace(
            image_url=f"https://i.gyazo.com/{filename}.png"
        )


class _FailingGyazoClient(_GyazoClient):
    async def upload_image(self, image, filename):
        if filename == "イオリ(水着).png":
            raise RuntimeError("Gyazo upload failed")
        return await super().upload_image(image, filename)


class _CosenseClient:
    def __init__(self, target_lines):
        self.target_lines = target_lines
        self.created_icons = []
        self.updates = []

    async def fetch_page(self, title):
        if title == "戦術対抗戦_略称":
            return {
                "lines": [
                    {"text": "戦術対抗戦_略称"},
                    {"text": " 水着"},
                    {"text": "  水"},
                ]
            }
        return {
            "created": 1234567890,
            "updated": 1234567899,
            "lines": [
                {
                    "text": line,
                    "created": 1234567890 + index,
                    "updated": 1234567890 + index,
                }
                for index, line in enumerate(self.target_lines)
            ],
        }

    async def fetch_target_page_titles(self):
        return ["対抗戦シーズン11_対戦相手"]

    async def icon_page_exists(self, student_name):
        return student_name == "エイミ"

    async def ensure_icon_page(self, student_name, image_url):
        self.created_icons.append((student_name, image_url))
        return True

    async def update_page_lines(self, title, lines, original_page):
        self.updates.append((title, lines, original_page))


class RefactorTargetPagesTest(unittest.IsolatedAsyncioTestCase):
    async def test_refactors_only_requested_target_page(self):
        wiki = _WikiClient()
        gyazo = _GyazoClient()
        cosense = _CosenseClient(["対象ページ", " エイミ、水イオリ"])
        cosense.fetch_target_page_titles = lambda: _async_value(
            ["対象ページ", "別ページ"]
        )

        results = await refactor_target_pages(
            wiki, gyazo, cosense, target_title="対象ページ"
        )

        self.assertEqual([result.title for result in results], ["対象ページ"])

    async def test_creates_missing_icons_and_updates_only_changed_page(self):
        wiki = _WikiClient()
        gyazo = _GyazoClient()
        cosense = _CosenseClient(
            [
                "対抗戦シーズン11_対戦相手",
                " 相手(水イオリ)",
                "  エイミ、水イオリ",
            ]
        )

        results = await refactor_target_pages(wiki, gyazo, cosense)

        expected_lines = [
            "対抗戦シーズン11_対戦相手",
            " 相手([!イオリ(水着).icon])",
            "  [!エイミ.icon]・[!イオリ(水着).icon]",
        ]
        self.assertEqual(
            results,
            [
                TargetPageResult(
                    title="対抗戦シーズン11_対戦相手",
                    changed_lines=2,
                    created_icons=("イオリ(水着)",),
                )
            ],
        )
        self.assertEqual(
            cosense.created_icons,
            [
                (
                    "イオリ(水着)",
                    "https://i.gyazo.com/イオリ(水着).png.png",
                )
            ],
        )
        self.assertEqual(
            cosense.updates,
            [
                (
                    "対抗戦シーズン11_対戦相手",
                    expected_lines,
                    {
                        "created": 1234567890,
                        "updated": 1234567899,
                        "lines": [
                            {
                                "text": line,
                                "created": 1234567890 + index,
                                "updated": 1234567890 + index,
                            }
                            for index, line in enumerate(
                                [
                                    "対抗戦シーズン11_対戦相手",
                                    " 相手(水イオリ)",
                                    "  エイミ、水イオリ",
                                ]
                            )
                        ],
                    },
                )
            ],
        )

    async def test_does_not_update_unchanged_page(self):
        wiki = _WikiClient()
        gyazo = _GyazoClient()
        lines = ["対抗戦シーズン11_対戦相手", " メモ"]
        cosense = _CosenseClient(lines)

        results = await refactor_target_pages(wiki, gyazo, cosense)

        self.assertEqual(
            results,
            [
                TargetPageResult(
                    title="対抗戦シーズン11_対戦相手",
                    changed_lines=0,
                    created_icons=(),
                )
            ],
        )
        self.assertEqual(cosense.updates, [])

    async def test_continues_refactoring_with_ready_icons_when_icon_creation_fails(self):
        wiki = _WikiClient()
        gyazo = _FailingGyazoClient()
        cosense = _CosenseClient(["対抗戦シーズン11_対戦相手", " エイミ、水イオリ"])

        results = await refactor_target_pages(wiki, gyazo, cosense)

        self.assertEqual(
            results,
            [
                TargetPageResult(
                    title="対抗戦シーズン11_対戦相手",
                    changed_lines=1,
                    created_icons=(),
                )
            ],
        )
        self.assertEqual(cosense.created_icons, [])
        self.assertEqual(
            cosense.updates[0][1],
            ["対抗戦シーズン11_対戦相手", " [!エイミ.icon]・水イオリ"],
        )


if __name__ == "__main__":
    unittest.main()


async def _async_value(value):
    return value
