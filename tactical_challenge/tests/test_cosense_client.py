import unittest

from tactical_challenge import (
    TargetPageParseError,
    build_page_update_import_data,
    parse_target_page_titles,
)


class ParseTargetPageTitlesTest(unittest.TestCase):
    def test_extracts_unique_page_titles_from_page_links(self):
        page_data = {
            "title": "戦術対抗戦_シーズン一覧",
            "links": [
                "対抗戦シーズン11_対戦相手",
                "対抗戦シーズン12_対戦相手",
                "対抗戦シーズン11_対戦相手",
            ],
        }

        titles = parse_target_page_titles(page_data)

        self.assertEqual(
            titles,
            [
                "対抗戦シーズン11_対戦相手",
                "対抗戦シーズン12_対戦相手",
            ],
        )

    def test_extracts_links_from_lines_when_page_links_are_missing(self):
        page_data = {
            "lines": [
                {"text": "戦術対抗戦_シーズン一覧", "links": []},
                {
                    "text": "[対抗戦シーズン11_対戦相手]",
                    "links": ["対抗戦シーズン11_対戦相手"],
                },
                {"text": "[対抗戦シーズン12_対戦相手]"},
            ]
        }

        titles = parse_target_page_titles(page_data)

        self.assertEqual(
            titles,
            [
                "対抗戦シーズン11_対戦相手",
                "対抗戦シーズン12_対戦相手",
            ],
        )

    def test_rejects_page_without_targets(self):
        with self.assertRaisesRegex(TargetPageParseError, "登録されていません"):
            parse_target_page_titles({"links": []})

    def test_ignores_hashtag_in_page_links(self):
        page_data = {
            "links": ["対抗戦シーズン11_対戦相手", "戦術対抗戦"],
            "lines": [
                {"text": "戦術対抗戦_シーズン一覧"},
                {"text": " [対抗戦シーズン11_対戦相手]"},
                {"text": "#戦術対抗戦"},
            ],
        }

        self.assertEqual(
            parse_target_page_titles(page_data),
            ["対抗戦シーズン11_対戦相手"],
        )

    def test_accepts_indented_target_link_with_tag(self):
        self.assertEqual(
            parse_target_page_titles(
                {
                    "title": "戦術対抗戦_シーズン一覧",
                    "lines": [
                        {"text": "戦術対抗戦_シーズン一覧"},
                        {"text": " [対抗戦シーズン11_対戦相手]"},
                        {"text": "#戦術対抗戦"},
                    ],
                }
            ),
            ["対抗戦シーズン11_対戦相手"],
        )


class BuildPageUpdateImportDataTest(unittest.TestCase):
    def test_builds_complete_page_update_data(self):
        self.assertEqual(
            build_page_update_import_data(
                "対抗戦シーズン11_対戦相手",
                ["対抗戦シーズン11_対戦相手", " [!エイミ.icon]"],
                1234567890,
                [
                    {
                        "text": "対抗戦シーズン11_対戦相手",
                        "created": 1234567890,
                        "updated": 1234567891,
                    },
                    {
                        "text": " エイミ",
                        "created": 1234567892,
                        "updated": 1234567893,
                    },
                ],
                1234567999,
            ),
            {
                "pages": [
                    {
                        "title": "対抗戦シーズン11_対戦相手",
                        "created": 1234567890,
                        "updated": 1234567999,
                        "lines": [
                            {
                                "text": "対抗戦シーズン11_対戦相手",
                                "created": 1234567890,
                                "updated": 1234567891,
                            },
                            {
                                "text": " [!エイミ.icon]",
                                "created": 1234567892,
                                "updated": 1234567999,
                            },
                        ],
                    }
                ]
            },
        )

    def test_uses_update_time_for_a_new_line(self):
        data = build_page_update_import_data(
            "対象ページ",
            ["対象ページ", " 追加行"],
            100,
            [{"text": "対象ページ", "created": 100, "updated": 101}],
            200,
        )

        self.assertEqual(
            data["pages"][0]["lines"][1],
            {"text": " 追加行", "created": 200, "updated": 200},
        )


if __name__ == "__main__":
    unittest.main()
