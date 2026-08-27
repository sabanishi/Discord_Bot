from pathlib import Path
import unittest

from tactical_challenge.wiki_parser import (
    WikiIconParseError,
    parse_student_icons,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "character_icons.html"
BASE_URL = "https://bluearchive.wikiru.jp/"


class ParseStudentIconsTest(unittest.TestCase):
    def test_extracts_names_and_absolute_image_urls(self):
        html = FIXTURE_PATH.read_text(encoding="utf-8")

        icons = parse_student_icons(html, BASE_URL)

        self.assertEqual(
            [(icon.name, icon.image_url) for icon in icons],
            [
                (
                    "イオリ(水着)",
                    "https://bluearchive.wikiru.jp/attach2/iori-swimsuit.png",
                ),
                (
                    "ホシノ(臨戦)",
                    "https://bluearchive.wikiru.jp/attach/hoshino-battle.png",
                ),
            ],
        )

    def test_prefers_lazy_loaded_data_src(self):
        html = FIXTURE_PATH.read_text(encoding="utf-8")

        icons = parse_student_icons(html, BASE_URL)

        self.assertNotIn("data:image", icons[0].image_url)

    def test_preserves_full_width_star_in_name(self):
        html = """
        <a title="シロコ＊テラー">
          <img src="attach/kuroko.png" alt="シロコ＊テラー_icon.png">
        </a>
        """

        icons = parse_student_icons(html, BASE_URL)

        self.assertEqual(icons[0].name, "シロコ＊テラー")

    def test_rejects_html_without_character_icons(self):
        with self.assertRaisesRegex(
            WikiIconParseError,
            "キャラアイコンを1件も取得できませんでした",
        ):
            parse_student_icons("<html><body></body></html>", BASE_URL)

    def test_keeps_first_image_when_a_name_has_alternate_images(self):
        html = """
        <a title="イオリ"><img src="attach/a.png" alt="イオリ_icon.png"></a>
        <a title="イオリ"><img src="attach/b.png" alt="イオリB_icon.png"></a>
        """

        icons = parse_student_icons(html, BASE_URL)

        self.assertEqual(len(icons), 1)
        self.assertEqual(
            icons[0].image_url,
            "https://bluearchive.wikiru.jp/attach/a.png",
        )


if __name__ == "__main__":
    unittest.main()
