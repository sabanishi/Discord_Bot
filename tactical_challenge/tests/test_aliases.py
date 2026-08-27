from pathlib import Path
import unittest

from tactical_challenge import (
    AliasConfig,
    AliasCollisionError,
    AliasRuleParseError,
    StudentIcon,
    build_student_aliases,
    parse_alias_rules,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "alias_rules.txt"


class ParseAliasRulesTest(unittest.TestCase):
    def test_parses_indented_aliases(self):
        rules = parse_alias_rules(
            FIXTURE_PATH.read_text(encoding="utf-8").splitlines()
        )

        self.assertEqual(
            rules.variant_aliases,
            {
                "水着": ("水",),
                "正月": ("正",),
                "ドレス": ("ド",),
                "バニーガール": ("バニー", "バニ", "バ"),
                "臨戦": (),
                "制服": (),
                "ガイド": (),
                "マジカル": (),
            },
        )
        self.assertEqual(
            rules.direct_aliases,
            {"クロコ": "シロコ＊テラー"},
        )

    def test_rejects_alias_without_variant(self):
        with self.assertRaisesRegex(AliasRuleParseError, "衣装名より前"):
            parse_alias_rules([" 水"])

    def test_rejects_duplicate_variant(self):
        with self.assertRaisesRegex(AliasRuleParseError, "重複"):
            parse_alias_rules(["水着", " 水", "水着", " 水着"])

    def test_parses_actual_page_with_common_indent_blank_lines_and_tag(self):
        rules = parse_alias_rules(
            [
                "戦術対抗戦_略称",
                "",
                " 水着   ",
                "  水 ",
                "   ",
                " 正月",
                "  正",
                "",
                " ドレス",
                "  ド",
                "",
                " バニーガール",
                "  バニー",
                "  バニ",
                "  バ",
                "",
                " クロコ   ->   シロコ＊テラー ",
                "",
                "#戦術対抗戦",
                "",
            ]
        )

        self.assertEqual(
            rules,
            AliasConfig(
                variant_aliases={
                    "水着": ("水",),
                    "正月": ("正",),
                    "ドレス": ("ド",),
                    "バニーガール": ("バニー", "バニ", "バ"),
                },
                direct_aliases={"クロコ": "シロコ＊テラー"},
            ),
        )


class BuildStudentAliasesTest(unittest.TestCase):
    def test_builds_canonical_full_and_short_variant_names(self):
        students = [
            StudentIcon("イオリ(水着)", "https://bluearchive.wikiru.jp/iori.png"),
            StudentIcon("クロコ", "https://bluearchive.wikiru.jp/kuroko.png"),
        ]

        aliases = build_student_aliases(
            students,
            AliasConfig({"水着": ("水",)}, {}),
        )

        self.assertEqual(
            aliases,
            {
                "イオリ(水着)": "イオリ(水着)",
                "水着イオリ": "イオリ(水着)",
                "水イオリ": "イオリ(水着)",
                "クロコ": "クロコ",
            },
        )

    def test_normalizes_full_width_parentheses(self):
        students = [
            StudentIcon("イオリ（水着）", "https://bluearchive.wikiru.jp/iori.png"),
        ]

        aliases = build_student_aliases(
            students,
            AliasConfig({"水着": ("水",)}, {}),
        )

        self.assertEqual(aliases["水イオリ"], "イオリ(水着)")

    def test_detects_alias_collision(self):
        students = [
            StudentIcon("ア(水着)", "https://bluearchive.wikiru.jp/a.png"),
            StudentIcon("水ア", "https://bluearchive.wikiru.jp/b.png"),
        ]

        with self.assertRaisesRegex(AliasCollisionError, "水ア"):
            build_student_aliases(
                students,
                AliasConfig({"水着": ("水",)}, {}),
            )

    def test_builds_short_bunny_and_direct_aliases(self):
        students = [
            StudentIcon(
                "ネル(バニーガール)",
                "https://bluearchive.wikiru.jp/neru.png",
            ),
            StudentIcon(
                "シロコ＊テラー",
                "https://bluearchive.wikiru.jp/kuroko.png",
            ),
        ]
        config = AliasConfig(
            {"バニーガール": ("バ",)},
            {"クロコ": "シロコ＊テラー"},
        )

        aliases = build_student_aliases(students, config)

        self.assertEqual(aliases["バネル"], "ネル(バニーガール)")
        self.assertEqual(aliases["クロコ"], "シロコ＊テラー")

    def test_rejects_direct_alias_for_unknown_student(self):
        students = [
            StudentIcon("シロコ", "https://bluearchive.wikiru.jp/shiroko.png"),
        ]

        with self.assertRaisesRegex(AliasRuleParseError, "Wikiにありません"):
            build_student_aliases(
                students,
                AliasConfig({}, {"クロコ": "シロコ＊テラー"}),
            )


if __name__ == "__main__":
    unittest.main()
