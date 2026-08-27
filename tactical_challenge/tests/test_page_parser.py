from pathlib import Path
import unittest

from tactical_challenge import (
    StudentIcon,
    build_student_aliases,
    extract_page_students,
    parse_alias_rules,
    refactor_page_lines,
)


FIXTURES = Path(__file__).parent / "fixtures"


class ExtractPageStudentsTest(unittest.TestCase):
    def test_extracts_opponent_icons_and_formation_students(self):
        canonical_names = [
            "イオリ(水着)",
            "シロコ＊テラー",
            "エイミ",
            "ホシノ",
            "ウタハ",
            "シロコ(水着)",
            "ユウカ",
            "イロハ(水着)",
            "マキ",
            "ツバキ",
            "ハナコ(水着)",
            "ミチル(ドレス)",
            "ユズ",
            "ホシノ(臨戦)",
            "ヒビキ",
            "レイサ(マジカル)",
            "ヒナ(水着)",
            "ネル(制服)",
            "ワカモ",
            "シュン",
            "シュン(水着)",
            "シロコ",
            "ミカ",
            "ツバキ(ガイド)",
        ]
        students = [
            StudentIcon(name, f"https://bluearchive.wikiru.jp/{index}.png")
            for index, name in enumerate(canonical_names)
        ]
        config = parse_alias_rules(
            (FIXTURES / "alias_rules.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        aliases = build_student_aliases(students, config)
        lines = (
            (FIXTURES / "sample_opponents.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )

        actual = extract_page_students(lines, aliases)

        self.assertEqual(actual, canonical_names)


class RefactorPageLinesTest(unittest.TestCase):
    def setUp(self):
        self.canonical_names = [
            "シロコ＊テラー",
            "エイミ",
            "ホシノ",
            "イオリ(水着)",
            "ウタハ",
            "シロコ(水着)",
            "ユウカ",
            "イロハ(水着)",
            "マキ",
            "ツバキ",
            "ハナコ(水着)",
            "ミチル(ドレス)",
            "ユズ",
            "ホシノ(臨戦)",
            "ヒビキ",
            "レイサ(マジカル)",
            "ヒナ(水着)",
            "ネル(制服)",
            "ワカモ",
            "シュン",
            "シュン(水着)",
            "シロコ",
            "ミカ",
            "ツバキ(ガイド)",
        ]
        students = [
            StudentIcon(name, f"https://bluearchive.wikiru.jp/{index}.png")
            for index, name in enumerate(self.canonical_names)
        ]
        config = parse_alias_rules(
            (FIXTURES / "alias_rules.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )
        self.aliases = build_student_aliases(students, config)
        self.lines = (
            (FIXTURES / "sample_opponents.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )

    def test_refactors_opponent_icon_and_formation_lines(self):
        actual = refactor_page_lines(self.lines, self.aliases)
        expected = (
            (FIXTURES / "expected_refactored_opponents.txt")
            .read_text(encoding="utf-8")
            .splitlines()
        )

        self.assertEqual(actual, expected)

    def test_preserves_notes_and_indentation(self):
        actual = refactor_page_lines(self.lines, self.aliases)

        self.assertIn("　　　臨戦ホシノがシュンのタゲを吸う", actual)
        self.assertIn("　　　エイミはツバキの方が良いかも", actual)

    def test_is_idempotent(self):
        once = refactor_page_lines(self.lines, self.aliases)
        twice = refactor_page_lines(once, self.aliases)

        self.assertEqual(twice, once)

    def test_replaces_remaining_name_in_partially_refactored_formation(self):
        lines = [
            " [!エイミ.icon]、[!ホシノ.icon]、水イオリ、[!ツバキ.icon]",
        ]

        actual = refactor_page_lines(lines, self.aliases)

        self.assertEqual(
            actual,
            [
                " [!エイミ.icon]・[!ホシノ.icon]・"
                "[!イオリ(水着).icon]・[!ツバキ.icon]",
            ],
        )

    def test_refactors_formation_at_exactly_fifty_percent(self):
        lines = [" エイミ、未登録A、ホシノ、未登録B"]

        actual = refactor_page_lines(lines, self.aliases)

        self.assertEqual(
            actual,
            [" [!エイミ.icon]・未登録A・[!ホシノ.icon]・未登録B"],
        )

    def test_does_not_refactor_formation_below_fifty_percent(self):
        lines = [" エイミ、未登録A、未登録B"]

        actual = refactor_page_lines(lines, self.aliases)

        self.assertEqual(actual, [" エイミ・未登録A・未登録B"])

    def test_refactors_single_student_line(self):
        actual = refactor_page_lines(["　水イオリ"], self.aliases)

        self.assertEqual(actual, ["　[!イオリ(水着).icon]"])

    def test_does_not_refactor_parenthesized_name_in_note(self):
        lines = ["　　　編成についてのメモ(ホシノ)"]

        actual = refactor_page_lines(lines, self.aliases)

        self.assertEqual(actual, lines)

    def test_replaces_japanese_comma_with_middle_dot(self):
        lines = ["　エイミ、ホシノ、ツバキ"]

        actual = refactor_page_lines(lines, self.aliases)

        self.assertEqual(
            actual,
            ["　[!エイミ.icon]・[!ホシノ.icon]・[!ツバキ.icon]"],
        )


if __name__ == "__main__":
    unittest.main()
