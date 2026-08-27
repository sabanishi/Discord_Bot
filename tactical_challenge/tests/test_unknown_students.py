import unittest

from tactical_challenge import (
    AliasConfig,
    StudentIcon,
    build_student_aliases,
    find_unrecognized_students,
)


class FindUnrecognizedStudentsTest(unittest.TestCase):
    def setUp(self):
        students = [
            StudentIcon("エイミ", "https://bluearchive.wikiru.jp/eimi.png"),
            StudentIcon("ホシノ", "https://bluearchive.wikiru.jp/hoshino.png"),
            StudentIcon("ツバキ", "https://bluearchive.wikiru.jp/tsubaki.png"),
            StudentIcon(
                "イオリ(水着)",
                "https://bluearchive.wikiru.jp/iori-swimsuit.png",
            ),
        ]
        config = AliasConfig(
            variant_aliases={"水着": ("水",)},
            direct_aliases={},
        )
        self.aliases = build_student_aliases(students, config)

    def test_reports_unknown_formation_member_with_close_candidate(self):
        lines = ["　エイミ、ホシノ、ツバギ"]

        unknown = find_unrecognized_students(lines, self.aliases)

        self.assertEqual(unknown, {"ツバギ": ("ツバキ",)})

    def test_reports_unknown_member_without_candidate(self):
        lines = ["　エイミ、ホシノ、完全不明"]

        unknown = find_unrecognized_students(lines, self.aliases)

        self.assertEqual(unknown, {"完全不明": ()})

    def test_reports_unknown_opponent_icon(self):
        lines = [
            "　対戦相手(水イオり)",
            "　　エイミ、ホシノ",
        ]

        unknown = find_unrecognized_students(lines, self.aliases)

        self.assertEqual(unknown, {"水イオり": ("イオリ(水着)",)})

    def test_deduplicates_repeated_unknown_names(self):
        lines = [
            "　エイミ、ホシノ、ツバギ",
            "　ホシノ、エイミ、ツバギ",
        ]

        unknown = find_unrecognized_students(lines, self.aliases)

        self.assertEqual(unknown, {"ツバギ": ("ツバキ",)})

    def test_ignores_unknown_words_in_notes(self):
        lines = [
            "　　　ツバギの方が良いかも",
            "　　　編成についてのメモ(ツバギ)",
        ]

        unknown = find_unrecognized_students(lines, self.aliases)

        self.assertEqual(unknown, {})


if __name__ == "__main__":
    unittest.main()
