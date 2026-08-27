from pathlib import Path
import unittest

from tactical_challenge import (
    BlueArchiveWikiClient,
    build_student_aliases,
    extract_page_students,
    parse_alias_rules,
)
from tactical_challenge.tests.image_assertions import assert_image_bytes


FIXTURES = Path(__file__).parent / "fixtures"


class LiveWikiTest(unittest.IsolatedAsyncioTestCase):
    async def test_fetches_catalog_and_sample_image(self):
        """実サイトから一覧と代表画像を取得できることを確認する。"""
        client = BlueArchiveWikiClient()
        icons = await client.fetch_student_icons()
        icons_by_name = {icon.name: icon for icon in icons}

        self.assertGreaterEqual(len(icons), 300)
        sample = icons_by_name["イオリ(水着)"]
        image = await client.fetch_icon_image(sample.image_url)
        assert_image_bytes(self, image)

    async def test_fetches_all_images_from_sample_page(self):
        """提示された対抗戦本文から抽出した全生徒の画像を取得する。"""
        client = BlueArchiveWikiClient()
        icons = await client.fetch_student_icons()
        config = parse_alias_rules(
            (FIXTURES / "alias_rules.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        aliases = build_student_aliases(icons, config)
        page_lines = (
            (FIXTURES / "sample_opponents.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        names = extract_page_students(page_lines, aliases)
        icons_by_name = {icon.name: icon for icon in icons}

        self.assertEqual(len(names), 24)
        for name in names:
            with self.subTest(name=name):
                image = await client.fetch_icon_image(icons_by_name[name].image_url)
                assert_image_bytes(self, image)


if __name__ == "__main__":
    unittest.main()
