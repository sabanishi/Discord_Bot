import unittest

from tactical_challenge import PageChangeError, build_page_changes


class BuildPageChangesTest(unittest.TestCase):
    def test_returns_only_changed_lines_with_one_based_line_numbers(self):
        before = [
            "対抗戦ページ",
            "　ナナこみ(水イオリ)",
            "　　クロコ、エイミ",
            "　　　メモ",
        ]
        after = [
            "対抗戦ページ",
            "　ナナこみ([!イオリ(水着).icon])",
            "　　[!シロコ＊テラー.icon]、[!エイミ.icon]",
            "　　　メモ",
        ]

        changes = build_page_changes(before, after)

        self.assertEqual(
            [
                (change.line_number, change.before, change.after)
                for change in changes
            ],
            [
                (
                    2,
                    "　ナナこみ(水イオリ)",
                    "　ナナこみ([!イオリ(水着).icon])",
                ),
                (
                    3,
                    "　　クロコ、エイミ",
                    "　　[!シロコ＊テラー.icon]、[!エイミ.icon]",
                ),
            ],
        )

    def test_returns_empty_list_when_page_is_unchanged(self):
        lines = ["対抗戦ページ", "　　　メモ"]

        changes = build_page_changes(lines, list(lines))

        self.assertEqual(changes, [])

    def test_rejects_different_line_counts(self):
        with self.assertRaisesRegex(PageChangeError, "行数"):
            build_page_changes(["1行目"], ["1行目", "2行目"])


if __name__ == "__main__":
    unittest.main()
