import os
import unittest
from pathlib import Path

from tactical_challenge import (
    AliasConfig,
    BlueArchiveWikiClient,
    GyazoClient,
    TacticalChallengeCosenseClient,
    build_page_changes,
    build_student_aliases,
    extract_page_students,
    parse_alias_rules,
    refactor_page_lines,
    refactor_target_pages,
)
from tactical_challenge.tests.env_loader import load_test_env


load_test_env(Path(__file__).parents[2] / ".env")


class LiveCosenseTest(unittest.IsolatedAsyncioTestCase):
    async def test_refactors_real_target_pages_and_is_idempotent(self):
        """実際の対象ページを更新し、2回目が無変更になることを確認する。"""
        project = os.getenv("COSENSE_PROJECT")
        sid = os.getenv("COSENSE_SID")
        gyazo_access_token = os.getenv("GYAZO_ACCESS_TOKEN")
        self.assertTrue(project, "COSENSE_PROJECTが必要です")
        self.assertTrue(sid, "COSENSE_SIDが必要です")
        self.assertTrue(gyazo_access_token, "GYAZO_ACCESS_TOKENが必要です")

        cosense = TacticalChallengeCosenseClient(project=project, sid=sid)
        wiki = BlueArchiveWikiClient()
        gyazo = GyazoClient(gyazo_access_token)
        alias_page = await cosense.fetch_page("戦術対抗戦_略称")
        config = parse_alias_rules(line["text"] for line in alias_page["lines"])
        icons = await wiki.fetch_student_icons()
        aliases = build_student_aliases(icons, config)
        titles = await cosense.fetch_target_page_titles()
        before_pages = {}
        for title in titles:
            page = await cosense.fetch_page(title)
            lines = [line["text"] for line in page["lines"]]
            expected = refactor_page_lines(lines, aliases)
            before_pages[title] = {
                "created": page["created"],
                "lines": lines,
                "expected": expected,
                "changes": len(build_page_changes(lines, expected)),
            }

        results = await refactor_target_pages(wiki, gyazo, cosense)
        results_by_title = {result.title: result for result in results}
        after_snapshots = {}
        for title in titles:
            with self.subTest(title=title):
                page = await cosense.fetch_page(title)
                lines = [line["text"] for line in page["lines"]]
                self.assertIs(page["persistent"], True)
                self.assertEqual(page["created"], before_pages[title]["created"])
                self.assertEqual(lines, before_pages[title]["expected"])
                self.assertEqual(
                    results_by_title[title].changed_lines,
                    before_pages[title]["changes"],
                )
                for student_name in extract_page_students(lines, aliases):
                    self.assertTrue(
                        await cosense.icon_page_exists(student_name),
                        f"{student_name}のアイコンページがありません",
                    )
                after_snapshots[title] = {
                    "created": page["created"],
                    "updated": page["updated"],
                    "lines": lines,
                }

        second_results = await refactor_target_pages(wiki, gyazo, cosense)
        self.assertTrue(
            all(result.changed_lines == 0 for result in second_results)
        )
        self.assertTrue(
            all(result.created_icons == () for result in second_results)
        )
        for title in titles:
            page = await cosense.fetch_page(title)
            self.assertEqual(
                {
                    "created": page["created"],
                    "updated": page["updated"],
                    "lines": [line["text"] for line in page["lines"]],
                },
                after_snapshots[title],
            )

    async def test_parses_real_alias_configuration_page(self):
        """実際の略称ページを取得し、規則全体を解析する。"""
        project = os.getenv("COSENSE_PROJECT")
        sid = os.getenv("COSENSE_SID")
        self.assertTrue(project, "COSENSE_PROJECTが必要です")
        self.assertTrue(sid, "COSENSE_SIDが必要です")

        client = TacticalChallengeCosenseClient(project=project, sid=sid)
        page = await client.fetch_page("戦術対抗戦_略称")
        self.assertEqual(page["title"], "戦術対抗戦_略称")
        self.assertIs(page["persistent"], True)
        rules = parse_alias_rules(
            line["text"]
            for line in page["lines"]
            if isinstance(line.get("text"), str)
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

    async def test_fetches_target_pages_from_season_list(self):
        """実際のCosense APIからシーズン一覧の対象ページを取得する。"""
        project = os.getenv("COSENSE_PROJECT")
        sid = os.getenv("COSENSE_SID")

        self.assertTrue(
            project,
            "Cosense API接続テストにはCOSENSE_PROJECTが必要です",
        )
        self.assertTrue(
            sid,
            "Cosense API接続テストにはCOSENSE_SIDが必要です",
        )

        client = TacticalChallengeCosenseClient(project=project, sid=sid)
        target_pages = await client.fetch_target_page_titles()

        self.assertGreater(len(target_pages), 0)
        self.assertTrue(all(title.strip() for title in target_pages))
        for title in target_pages:
            with self.subTest(title=title):
                page = await client.fetch_page(title)
                self.assertEqual(page["title"], title)
                self.assertIs(page["persistent"], True)
                self.assertGreater(len(page["lines"]), 1)

    async def test_ensures_real_icon_pages_exist_without_recreating_them(self):
        """実APIで不足アイコンを作成し、既存ページは再作成しない。"""
        project = os.getenv("COSENSE_PROJECT")
        sid = os.getenv("COSENSE_SID")
        gyazo_access_token = os.getenv("GYAZO_ACCESS_TOKEN")
        self.assertTrue(project, "COSENSE_PROJECTが必要です")
        self.assertTrue(sid, "COSENSE_SIDが必要です")
        self.assertTrue(gyazo_access_token, "GYAZO_ACCESS_TOKENが必要です")

        students = {
            "イオリ(水着)": "iori_swimsuit.png",
            "シロコ＊テラー": "shiroko_terror.png",
            "ネル(制服)": "neru_school_uniform.png",
        }
        client = TacticalChallengeCosenseClient(project=project, sid=sid)
        missing_students = [
            name
            for name in students
            if not await client.icon_page_exists(name)
        ]
        if missing_students:
            wiki_client = BlueArchiveWikiClient()
            icons = await wiki_client.fetch_student_icons()
            icons_by_name = {icon.name: icon for icon in icons}
            gyazo_client = GyazoClient(gyazo_access_token)
            for student_name in missing_students:
                image = await wiki_client.fetch_icon_image(
                    icons_by_name[student_name].image_url
                )
                upload = await gyazo_client.upload_image(
                    image,
                    students[student_name],
                )
                created = await client.ensure_icon_page(
                    student_name,
                    upload.image_url,
                )
                self.assertTrue(created)

        for student_name in students:
            with self.subTest(student_name=student_name):
                self.assertTrue(await client.icon_page_exists(student_name))
                page = await client.fetch_icon_page(student_name)
                self.assertEqual(
                    page["title"],
                    f"!{student_name}",
                )
                self.assertIs(page["persistent"], True)
                self.assertEqual(page["created"], 1)
                body_lines = [
                    line["text"]
                    for line in page["lines"][1:]
                    if isinstance(line.get("text"), str)
                ]
                self.assertTrue(
                    any(
                        line.startswith("[https://i.gyazo.com/")
                        and line.endswith("]")
                        for line in body_lines
                    ),
                    f"!{student_name}にGyazo画像URLがありません",
                )
                self.assertTrue(
                    page["image"].startswith("https://i.gyazo.com/"),
                    f"!{student_name}のページタイトル画像が未設定です",
                )
                body_image_url = next(
                    line[1:-1]
                    for line in body_lines
                    if line.startswith("[https://i.gyazo.com/")
                    and line.endswith("]")
                )
                self.assertEqual(
                    page["image"].removesuffix("/raw"),
                    body_image_url,
                )
                self.assertEqual(
                    [line for line in body_lines if line],
                    [
                        f"[{body_image_url}]",
                        " This page was auto generated.",
                        "#戦術対抗戦_アイコン",
                    ],
                )
                before = {
                    "updated": page["updated"],
                    "image": page["image"],
                    "lines": [line["text"] for line in page["lines"]],
                }
                self.assertFalse(
                    await client.ensure_icon_page(
                        student_name,
                        "https://i.gyazo.com/unused-test-image.png",
                    )
                )
                after_page = await client.fetch_icon_page(student_name)
                after = {
                    "updated": after_page["updated"],
                    "image": after_page["image"],
                    "lines": [line["text"] for line in after_page["lines"]],
                }
                self.assertEqual(after, before)


if __name__ == "__main__":
    unittest.main()
