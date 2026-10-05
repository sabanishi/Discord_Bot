import copy
import asyncio
import unittest
import json
from urllib.parse import unquote, urlparse

from app.mirroring import (
    build_import_data,
    build_page_data_export_url,
    MirrorCosenseClient,
    parse_exclusion_settings,
    parse_replacement_settings,
    transform_exported_pages,
)


class ExportedPageTransformationTests(unittest.TestCase):
    def test_excludes_pages_without_removing_links_to_excluded_pages(self):
        pages = [
            {
                "title": "公開ページ",
                "created": 100,
                "updated": 200,
                "lines": [
                    {"text": "公開ページ", "created": 100},
                    {"text": "[非公開ページ] [https://example.com/file.png]"},
                ],
            },
            {
                "title": "非公開ページ",
                "created": 101,
                "lines": [
                    {"text": "非公開ページ", "created": 101},
                    {"text": "#diary"},
                ],
            },
        ]

        result = transform_exported_pages(
            pages,
            excluded_tags={"#diary"},
            excluded_icons=set(),
            replacements={},
        )

        self.assertEqual([page["title"] for page in result], ["公開ページ"])
        self.assertEqual(
            result[0]["lines"],
            [
                {"text": "公開ページ", "created": 100},
                {"text": "[非公開ページ] [https://example.com/file.png]"},
            ],
        )
        self.assertEqual(result[0]["created"], 100)
        self.assertEqual(result[0]["updated"], 200)

    def test_excludes_page_with_configured_icon(self):
        result = transform_exported_pages(
            [
                {
                    "title": "非公開アイコンページ",
                    "lines": [{"text": "非公開アイコンページ [private.icon]"}],
                },
                {"title": "公開ページ", "lines": [{"text": "公開ページ"}]},
            ],
            excluded_tags=set(),
            excluded_icons={"[private.icon]"},
            replacements={},
        )

        self.assertEqual([page["title"] for page in result], ["公開ページ"])

    def test_replaces_title_and_line_text_without_changing_metadata(self):
        pages = [
            {
                "title": "本名のページ",
                "created": 100,
                "updated": 200,
                "user": "author",
                "lines": [
                    {"text": "本名のページ", "created": 100},
                    {"text": "本名のメモ"},
                ],
            }
        ]

        result = transform_exported_pages(
            pages,
            excluded_tags=set(),
            excluded_icons=set(),
            replacements={"本名": "公開名"},
        )

        self.assertEqual(result[0]["title"], "公開名のページ")
        self.assertEqual(
            result[0]["lines"],
            [
                {"text": "公開名のページ", "created": 100},
                {"text": "公開名のメモ"},
            ],
        )
        self.assertEqual(result[0]["user"], "author")

    def test_updates_links_when_linked_title_is_replaced(self):
        result = transform_exported_pages(
            [
                {
                    "title": "本名ページ",
                    "lines": [{"text": "本名ページ"}],
                },
                {
                    "title": "リンク元",
                    "lines": [{"text": "[本名ページ]"}],
                },
            ],
            excluded_tags=set(),
            excluded_icons=set(),
            replacements={"本名": "公開"},
        )

        self.assertEqual(result[1]["lines"], [{"text": "[公開ページ]"}])

    def test_preserves_external_links_attachment_references_and_hashtags(self):
        result = transform_exported_pages(
            [
                {
                    "title": "ページ",
                    "lines": [
                        {
                            "text": "[https://example.com/a.png] [画像.png] #keep [未公開]"
                        }
                    ],
                }
            ],
            excluded_tags=set(),
            excluded_icons=set(),
            replacements={},
        )

        self.assertEqual(
            result[0]["lines"],
            [{"text": "[https://example.com/a.png] [画像.png] #keep [未公開]"}],
        )

    def test_preserves_scrapbox_decorations_icons_and_aliased_external_links(self):
        result = transform_exported_pages(
            [
                {
                    "title": "公開ページ",
                    "lines": [
                        {
                            "text": (
                                "[GitHub リポジトリ https://github.com/example/repo] "
                                "[水平線.icon] [/icons/水平線.icon] "
                                "[#<> 機能] [** 以下作業ログ] "
                                "[&.** [公開ページ]表示] "
                                "[.&** [非公開ページ]表示]"
                            )
                        }
                    ],
                }
            ],
            excluded_tags=set(),
            excluded_icons=set(),
            replacements={},
        )

        self.assertEqual(
            result[0]["lines"][0]["text"],
            (
                "[GitHub リポジトリ https://github.com/example/repo] "
                "[水平線.icon] [/icons/水平線.icon] "
                "[#<> 機能] [** 以下作業ログ] "
                "[&.** [公開ページ]表示] "
                "[.&** [非公開ページ]表示]"
            ),
        )

    def test_replacements_do_not_modify_external_links_or_attachment_references(self):
        result = transform_exported_pages(
            [
                {
                    "title": "ページ",
                    "lines": [
                        {"text": "[https://private.example/a.png] [private.png]"}
                    ],
                }
            ],
            excluded_tags=set(),
            excluded_icons=set(),
            replacements={"private": "public"},
        )

        self.assertEqual(
            result[0]["lines"],
            [{"text": "[https://private.example/a.png] [private.png]"}],
        )

    def test_prefers_public_page_link_over_attachment_extension(self):
        result = transform_exported_pages(
            [
                {"title": "report.pdf", "lines": [{"text": "report.pdf"}]},
                {"title": "案内", "lines": [{"text": "[report.pdf]"}]},
            ],
            excluded_tags=set(),
            excluded_icons=set(),
            replacements={"report": "公開"},
        )

        self.assertEqual(result[1]["lines"], [{"text": "[公開.pdf]"}])


class MirroringSettingsParserTests(unittest.TestCase):
    def test_parses_tags_and_icons(self):
        tags, icons = parse_exclusion_settings(
            ["設定", "#diary #研究", "[private.icon]"]
        )

        self.assertEqual(tags, {"#diary", "#研究"})
        self.assertEqual(icons, {"[private.icon]"})

    def test_parses_replacement_pairs(self):
        self.assertEqual(
            parse_replacement_settings(["本名 => 公開名", "住所=>非公開", "無視"]),
            {"本名": "公開名", "住所": "非公開"},
        )

    def test_last_duplicate_replacement_wins_and_blank_lines_are_ignored(self):
        self.assertEqual(
            parse_replacement_settings(["", "本名 => 公開名", "本名 => 別名"]),
            {"本名": "別名"},
        )

    def test_rejects_invalid_replacement_pair(self):
        with self.assertRaisesRegex(ValueError, "置換設定"):
            parse_replacement_settings(["=> 公開名"])


class MirroringApiDataTests(unittest.TestCase):
    def test_builds_metadata_export_url(self):
        self.assertEqual(
            build_page_data_export_url("private project"),
            "https://scrapbox.io/api/page-data/export/private%20project.json?metadata=true",
        )

    def test_builds_import_data_without_dropping_metadata(self):
        pages = [{"title": "ページ", "created": 1, "lines": []}]

        self.assertEqual(build_import_data(pages), {"pages": pages})


class MirroringClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_exports_pages_with_metadata_and_imports_saved_pages(self):
        session = _HttpSession(
            get_body='{"pages": [{"title": "ページ", "lines": []}]}',
        )
        client = MirrorCosenseClient("private", "connect.sid=session", session=session)

        pages = await client.export_pages()
        await client.import_pages(pages)

        self.assertEqual(pages[0]["title"], "ページ")
        self.assertEqual(session.calls[0][0], "get")
        self.assertEqual(
            session.calls[0][1],
            "https://scrapbox.io/api/page-data/export/private.json?metadata=true",
        )
        self.assertEqual(session.calls[1][0], "post")
        self.assertEqual(session.calls[1][2]["Cookie"], "connect.sid=session")
        self.assertEqual(session.calls[1][2]["Origin"], "https://scrapbox.io")
        self.assertEqual(
            session.calls[1][2]["Referer"],
            "https://scrapbox.io/private/settings/page-data",
        )
        form = session.calls[1][3]
        self.assertEqual(len(form._fields), 1)
        self.assertEqual(form._fields[0][0]["name"], "import-file")
        payload = json.loads(form._fields[0][2].decode("utf-8"))
        self.assertEqual(payload, {"pages": pages})

    async def test_deletes_page_with_encoded_title(self):
        session = _HttpSession()
        client = MirrorCosenseClient("public project", "sid", session=session)

        await client.delete_page("削除対象")

        self.assertEqual(session.calls[0][0], "delete")
        self.assertIn("%E5%89%8A%E9%99%A4%E5%AF%BE%E8%B1%A1", session.calls[0][1])
        self.assertEqual(session.calls[0][2]["Cookie"], "connect.sid=sid")

    async def test_import_url_encodes_project_name(self):
        session = _HttpSession()
        client = MirrorCosenseClient("public project", "sid", session=session)

        await client.import_pages([])

        self.assertIn("/import/public%20project.json", session.calls[0][1])

    async def test_rejects_export_server_error(self):
        session = _HttpSession(status=503, get_body="server error")
        client = MirrorCosenseClient("private", "sid", session=session)

        with self.assertRaisesRegex(RuntimeError, "status=503"):
            await client.export_pages()

    async def test_rejects_invalid_export_json(self):
        session = _HttpSession(get_body="not-json")
        client = MirrorCosenseClient("private", "sid", session=session)

        with self.assertRaisesRegex(RuntimeError, "不正なJSON"):
            await client.export_pages()

    async def test_rejects_export_json_with_invalid_pages_value(self):
        session = _HttpSession(get_body='{"pages": {}}')
        client = MirrorCosenseClient("private", "sid", session=session)

        with self.assertRaisesRegex(RuntimeError, "pagesが不正"):
            await client.export_pages()

    async def test_rejects_export_page_without_required_fields(self):
        session = _HttpSession(
            get_body='{"pages": [{"title": "ページ"}]}'
        )
        client = MirrorCosenseClient("private", "sid", session=session)

        with self.assertRaisesRegex(RuntimeError, "必須項目"):
            await client.export_pages()

    async def test_rejects_page_json_that_is_not_an_object(self):
        session = _HttpSession(get_body="[]")
        client = MirrorCosenseClient("private", "sid", session=session)

        with self.assertRaisesRegex(RuntimeError, "レスポンス形式"):
            await client.fetch_page("設定")

    async def test_fetches_page_with_project_and_title_encoding_and_cookie(self):
        session = _HttpSession(get_body='{"title": "設定"}')
        client = MirrorCosenseClient("private project", "connect.sid=session", session=session)

        page = await client.fetch_page("設定ページ")

        self.assertEqual(page, {"title": "設定"})
        self.assertEqual(session.calls[0][0], "get")
        self.assertIn("private%20project", session.calls[0][1])
        self.assertIn("%E8%A8%AD%E5%AE%9A%E3%83%9A%E3%83%BC%E3%82%B8", session.calls[0][1])
        self.assertEqual(session.calls[0][2]["Cookie"], "connect.sid=session")

    async def test_rejects_delete_server_error(self):
        session = _HttpSession(status=500, get_body="delete failed")
        client = MirrorCosenseClient("public", "sid", session=session)

        with self.assertRaisesRegex(RuntimeError, "status=500"):
            await client.delete_page("ページ")

    async def test_rejects_import_server_error(self):
        session = _HttpSession(status=500)
        client = MirrorCosenseClient("public", "sid", session=session)

        with self.assertRaisesRegex(RuntimeError, "status=500"):
            await client.import_pages([{"title": "ページ", "lines": []}])

    async def test_propagates_timeout_from_export_request(self):
        client = MirrorCosenseClient(
            "private", "sid", session=_RaisingHttpSession(asyncio.TimeoutError())
        )

        with self.assertRaises(asyncio.TimeoutError):
            await client.export_pages()

    async def test_rejects_malformed_setting_page(self):
        session = _HttpSession(get_body='{"lines": [{"text": 123}]}')
        client = MirrorCosenseClient("private", "sid", session=session)

        with self.assertRaisesRegex(RuntimeError, "行形式"):
            await client.fetch_page_lines("設定")


class _HttpResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def text(self):
        return self.body


class _HttpSession:
    def __init__(self, get_body="{}", status=200):
        self.get_body = get_body
        self.status = status
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def get(self, url, headers):
        self.calls.append(("get", url, headers))
        return _HttpResponse(self.get_body, self.status)

    def post(self, url, headers, data):
        self.calls.append(("post", url, headers, data))
        return _HttpResponse("imported", self.status)

    def delete(self, url, headers):
        self.calls.append(("delete", url, headers))
        return _HttpResponse("deleted", self.status)


class _RaisingHttpSession:
    def __init__(self, error):
        self.error = error

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def get(self, url, headers):
        raise self.error


class _StatefulHttpSession:
    def __init__(self, project, pages, config_pages=None):
        self.project = project
        self.pages = copy.deepcopy(pages)
        self.config_pages = config_pages or {}

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    def get(self, url, headers):
        parsed = urlparse(url)
        if "/page-data/export/" in parsed.path:
            body = json.dumps({"pages": self.pages}, ensure_ascii=False)
        else:
            title = unquote(parsed.path.rsplit("/", maxsplit=1)[-1])
            body = json.dumps(self.config_pages[title], ensure_ascii=False)
        return _HttpResponse(body)

    def post(self, url, headers, data):
        payload = json.loads(data._fields[0][2].decode("utf-8"))
        imported = payload["pages"]
        imported_by_title = {page["title"]: copy.deepcopy(page) for page in imported}
        preserved = [
            page for page in self.pages if page["title"] not in imported_by_title
        ]
        self.pages = preserved + list(imported_by_title.values())
        return _HttpResponse("imported")

    def delete(self, url, headers):
        title = unquote(urlparse(url).path.rsplit("/", maxsplit=1)[-1])
        self.pages = [page for page in self.pages if page["title"] != title]
        return _HttpResponse("deleted")


class MirroringServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_works_through_real_clients_against_stateful_http_mocks(self):
        from app.mirroring import MirrorCosenseClient, MirrorService

        source_session = _StatefulHttpSession(
            project="private",
            pages=[
                {
                    "title": "本名ページ",
                    "created": 1,
                    "updated": 2,
                    "lines": [{"text": "本名ページ"}, {"text": "本名"}],
                },
                {
                    "title": "日記",
                    "lines": [{"text": "日記"}, {"text": "#diary"}],
                },
            ],
            config_pages={
                "除外設定": {"lines": [{"text": "#diary"}]},
                "置換設定": {"lines": [{"text": "本名 => 公開名"}]},
            },
        )
        destination_session = _StatefulHttpSession(
            project="public",
            pages=[{"title": "削除対象", "lines": [{"text": "削除対象"}]}],
        )

        result = await MirrorService(
            MirrorCosenseClient("private", "sid", session=source_session),
            MirrorCosenseClient("public", "sid", session=destination_session),
            "除外設定",
            "置換設定",
        ).run()

        self.assertEqual(result.created_pages, 1)
        self.assertEqual(result.updated_pages, 0)
        self.assertEqual(result.deleted_titles, ["削除対象"])
        self.assertEqual(
            destination_session.pages,
            [
                {
                    "title": "公開名ページ",
                    "created": 1,
                    "updated": 2,
                    "lines": [{"text": "公開名ページ"}, {"text": "公開名"}],
                }
            ],
        )

    async def test_run_accepts_destination_generated_page_id(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {
                    "title": "ページ",
                    "id": "private-id",
                    "lines": [{"text": "ページ"}],
                }
            ]
        )
        destination = _FakeCosenseClient(
            pages=[
                {
                    "title": "ページ",
                    "id": "public-id",
                    "lines": [{"text": "ページ"}],
                }
            ]
        )

        result = await MirrorService(source, destination, "", "").run()

        self.assertEqual(result.updated_pages, 1)
        self.assertEqual(destination.import_calls, 1)

    async def test_saved_page_verification_accepts_generated_line_ids(self):
        from app.mirroring import _verify_saved_pages

        expected = [
            {
                "title": "ページ",
                "id": "private-page-id",
                "lines": [
                    {"id": "private-line-id", "text": "ページ", "created": 1}
                ],
            }
        ]
        saved = [
            {
                "title": "ページ",
                "id": "public-page-id",
                "lines": [
                    {"id": "public-line-id", "text": "ページ", "created": 999}
                ],
            }
        ]

        _verify_saved_pages(expected, saved, [])

    async def test_run_exports_transforms_and_imports_pages(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {
                    "title": "公開ページ",
                    "created": 100,
                    "updated": 200,
                    "user": "author",
                    "lines": [{"text": "公開ページ"}],
                },
                {
                    "title": "日記",
                    "lines": [{"text": "日記"}, {"text": "#diary"}],
                },
            ],
            config_pages={
                "除外設定": {"lines": [{"text": "#diary"}]},
                "置換設定": {"lines": [{"text": "本名 => 公開名"}]},
            },
        )
        destination = _FakeCosenseClient(
            pages=[{"title": "削除対象", "lines": [{"text": "削除対象"}]}]
        )

        result = await MirrorService(
            source,
            destination,
            exclusion_config_page="除外設定",
            replacement_config_page="置換設定",
        ).run()

        self.assertEqual(result.imported_pages, 1)
        self.assertEqual(result.created_pages, 1)
        self.assertEqual(result.updated_pages, 0)
        self.assertEqual(result.deleted_pages, 1)
        self.assertEqual(result.created_titles, ["公開ページ"])
        self.assertEqual(result.updated_titles, [])
        self.assertEqual(result.excluded_titles, ["日記"])
        self.assertEqual(result.failed_titles, [])
        self.assertEqual(result.deleted_titles, ["削除対象"])
        self.assertEqual(destination.imported_pages[0]["title"], "公開ページ")
        self.assertEqual(destination.pages[-1]["created"], 100)
        self.assertEqual(destination.pages[-1]["updated"], 200)
        self.assertEqual(destination.pages[-1]["user"], "author")
        self.assertEqual(result.excluded_pages, 1)
        self.assertEqual(destination.deleted_titles, ["削除対象"])
        self.assertEqual(destination.export_calls, 2)
        self.assertEqual(destination.fetch_page_lines_calls, {})
        self.assertEqual(source.fetch_page_lines_calls, {"除外設定": 1, "置換設定": 1})

    async def test_run_deletes_public_copy_when_source_page_becomes_excluded(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {"title": "日記", "lines": [{"text": "日記"}, {"text": "#diary"}]},
                {"title": "公開", "lines": [{"text": "公開"}]},
            ]
        )
        destination = _FakeCosenseClient(
            pages=[
                {"title": "日記", "lines": [{"text": "日記"}]},
                {"title": "公開", "lines": [{"text": "古い内容"}]},
            ]
        )

        result = await MirrorService(source, destination, "", "").run()

        self.assertEqual(result.created_pages, 0)
        self.assertEqual(result.updated_pages, 1)
        self.assertEqual(result.deleted_pages, 1)
        self.assertEqual(destination.deleted_titles, ["日記"])
        saved = {page["title"]: page for page in destination.pages}
        self.assertNotIn("日記", saved)
        self.assertEqual(saved["公開"]["lines"], [{"text": "公開"}])

    async def test_run_applies_replacement_settings_to_titles_body_and_links(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {
                    "title": "本名ページ",
                    "lines": [{"text": "本名ページ"}, {"text": "本名の本文"}],
                },
                {
                    "title": "案内",
                    "lines": [{"text": "[本名ページ] 本名"}],
                },
            ],
            config_pages={
                "置換設定": {"lines": [{"text": "本名 => 公開名"}]},
            },
        )
        destination = _FakeCosenseClient(pages=[])

        await MirrorService(source, destination, "", "置換設定").run()

        saved = {page["title"]: page for page in destination.pages}
        self.assertEqual(saved["公開名ページ"]["lines"][1]["text"], "公開名の本文")
        self.assertEqual(saved["案内"]["lines"][0]["text"], "[公開名ページ] 公開名")

    async def test_run_rejects_when_saved_public_page_does_not_match(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[{"title": "ページ", "lines": [{"text": "期待値"}]}]
        )
        destination = _FakeCosenseClient(pages=[], tamper_after_import=True)

        with self.assertRaisesRegex(RuntimeError, "保存後の確認に失敗"):
            await MirrorService(
                source,
                destination,
                exclusion_config_page="",
                replacement_config_page="",
            ).run()

    async def test_run_continues_after_invalid_page(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {"title": "不正ページ", "lines": "invalid"},
                {"title": "正常ページ", "lines": [{"text": "正常ページ"}]},
            ]
        )
        destination = _FakeCosenseClient(pages=[])

        result = await MirrorService(
            source,
            destination,
            exclusion_config_page="",
            replacement_config_page="",
        ).run()

        self.assertEqual(result.imported_pages, 1)
        self.assertEqual(result.failed_pages, 1)
        self.assertEqual(result.failed_titles, ["不正ページ"])
        self.assertEqual(
            [page["title"] for page in destination.imported_pages], ["正常ページ"]
        )

    async def test_run_continues_after_page_title_is_missing(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {"lines": [{"text": "タイトルなし"}]},
                {"title": "正常ページ", "lines": [{"text": "正常ページ"}]},
            ]
        )
        destination = _FakeCosenseClient(pages=[])

        result = await MirrorService(source, destination, "", "").run()

        self.assertEqual(result.failed_pages, 1)
        self.assertEqual(result.failed_titles, [])
        self.assertEqual(
            [page["title"] for page in destination.imported_pages], ["正常ページ"]
        )

    async def test_run_does_not_delete_existing_page_when_source_page_is_invalid(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {"title": "壊れたページ", "lines": "invalid"},
                {"title": "正常ページ", "lines": [{"text": "正常ページ"}]},
            ]
        )
        destination = _FakeCosenseClient(
            pages=[
                {"title": "壊れたページ", "lines": [{"text": "既存内容"}]},
                {"title": "削除対象", "lines": [{"text": "削除対象"}]},
            ]
        )

        result = await MirrorService(
            source,
            destination,
            exclusion_config_page="",
            replacement_config_page="",
        ).run()

        self.assertEqual(result.failed_pages, 1)
        self.assertEqual(destination.deleted_titles, ["削除対象"])
        saved_titles = {page["title"] for page in destination.pages}
        self.assertIn("壊れたページ", saved_titles)

    async def test_run_protects_replaced_title_when_source_page_is_invalid(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {"title": "個人ページ", "lines": "invalid"},
                {"title": "正常ページ", "lines": [{"text": "正常ページ"}]},
            ],
            config_pages={
                "置換設定": {"lines": [{"text": "個人 => 公開"}]},
            },
        )
        destination = _FakeCosenseClient(
            pages=[
                {"title": "公開ページ", "lines": [{"text": "既存内容"}]},
                {"title": "削除対象", "lines": [{"text": "削除対象"}]},
            ]
        )

        result = await MirrorService(source, destination, "", "置換設定").run()

        self.assertEqual(result.failed_pages, 1)
        self.assertEqual(destination.deleted_titles, ["削除対象"])
        self.assertIn("公開ページ", {page["title"] for page in destination.pages})

    async def test_run_applies_default_exclusions_without_config_page_entries(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {"title": "日記", "lines": [{"text": "日記"}, {"text": "#diary"}]},
                {"title": "研究", "lines": [{"text": "研究"}, {"text": "#研究"}]},
                {
                    "title": "非公開アイコン",
                    "lines": [{"text": "非公開アイコン [private.icon]"}],
                },
                {"title": "公開", "lines": [{"text": "公開"}]},
            ]
        )
        destination = _FakeCosenseClient(pages=[])

        result = await MirrorService(
            source,
            destination,
            exclusion_config_page="",
            replacement_config_page="",
        ).run()

        self.assertEqual(result.excluded_pages, 3)
        self.assertEqual([page["title"] for page in destination.imported_pages], ["公開"])

    async def test_preview_returns_targets_and_replacements_without_public_writes(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {"title": "個人ページ", "lines": [{"text": "個人ページ"}]},
                {"title": "除外ページ", "lines": [{"text": "#secret"}]},
            ],
            config_pages={
                "除外設定": {"lines": [{"text": "#secret"}]},
                "置換設定": {"lines": [{"text": "個人 => 公開"}]},
            },
        )
        destination = _FakeCosenseClient(pages=[])

        result = await MirrorService(source, destination, "除外設定", "置換設定").preview()

        self.assertEqual(result.replacement_rules, {"個人": "公開"})
        self.assertEqual(result.included_titles, [("個人ページ", "公開ページ")])
        self.assertEqual(result.excluded_titles, ["除外ページ"])
        self.assertEqual(destination.export_calls, 0)
        self.assertEqual(destination.import_calls, 0)
        self.assertEqual(destination.deleted_titles, [])

    async def test_run_applies_custom_tags_and_icons_from_exclusion_page(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[
                {"title": "タグ除外", "lines": [{"text": "タグ除外 #secret"}]},
                {"title": "アイコン除外", "lines": [{"text": "[secret.icon]"}]},
                {"title": "公開", "lines": [{"text": "公開"}]},
            ],
            config_pages={
                "除外設定": {"lines": [{"text": "#secret [secret.icon]"}]},
            },
        )
        destination = _FakeCosenseClient(pages=[])

        result = await MirrorService(source, destination, "除外設定", "").run()

        self.assertEqual(result.excluded_pages, 2)
        self.assertEqual([page["title"] for page in destination.pages], ["公開"])

    async def test_run_does_not_write_when_exclusion_settings_cannot_be_loaded(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(pages=[], config_error=RuntimeError("設定取得失敗"))
        destination = _FakeCosenseClient(pages=[])

        with self.assertRaisesRegex(RuntimeError, "設定取得失敗"):
            await MirrorService(
                source,
                destination,
                exclusion_config_page="除外設定",
                replacement_config_page="",
            ).run()

        self.assertEqual(destination.import_calls, 0)
        self.assertEqual(destination.deleted_titles, [])

    async def test_run_stops_before_public_changes_when_source_export_fails(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(pages=[], export_error=ConnectionError("接続断"))
        destination = _FakeCosenseClient(
            pages=[{"title": "既存", "lines": [{"text": "既存"}]}]
        )

        with self.assertRaisesRegex(ConnectionError, "接続断"):
            await MirrorService(source, destination, "", "").run()

        self.assertEqual(destination.import_calls, 0)
        self.assertEqual(destination.deleted_titles, [])

    async def test_run_does_not_delete_stale_pages_when_public_import_fails(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[{"title": "公開", "lines": [{"text": "公開"}]}]
        )
        destination = _FakeCosenseClient(
            pages=[{"title": "削除対象", "lines": [{"text": "削除対象"}]}],
            import_error=RuntimeError("429 Too Many Requests"),
        )

        with self.assertRaisesRegex(RuntimeError, "429"):
            await MirrorService(source, destination, "", "").run()

        self.assertEqual(destination.deleted_titles, [])

    async def test_run_serializes_overlapping_executions(self):
        from app.mirroring import MirrorService

        source = _ConcurrencyTrackingClient(
            pages=[{"title": "ページ", "lines": [{"text": "ページ"}]}]
        )
        destination = _FakeCosenseClient(pages=[])
        service = MirrorService(source, destination, "", "")

        await asyncio.gather(service.run(), service.run())

        self.assertEqual(source.max_concurrent_exports, 1)

    async def test_run_is_idempotent_after_saved_state_is_reloaded(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(
            pages=[{"title": "ページ", "lines": [{"text": "ページ"}]}]
        )
        destination = _FakeCosenseClient(pages=[])
        service = MirrorService(source, destination, "", "")

        first = await service.run()
        second = await service.run()

        self.assertEqual(first.imported_pages, 1)
        self.assertEqual(second.imported_pages, 1)
        self.assertEqual(destination.deleted_titles, [])
        self.assertEqual(destination.import_calls, 2)

    async def test_run_is_one_way_and_does_not_modify_source_pages(self):
        from app.mirroring import MirrorService

        source_pages = [{"title": "原本", "lines": [{"text": "原本"}]}]
        source = _FakeCosenseClient(pages=source_pages)
        destination = _FakeCosenseClient(
            pages=[{"title": "原本", "lines": [{"text": "Public側の編集"}]}]
        )

        await MirrorService(source, destination, "", "").run()

        self.assertEqual(source.pages, source_pages)
        self.assertEqual(destination.pages[-1]["lines"], [{"text": "原本"}])

    async def test_run_continues_deleting_pages_after_one_delete_failure(self):
        from app.mirroring import MirrorService

        source = _FakeCosenseClient(pages=[])
        destination = _FakeCosenseClient(
            pages=[
                {"title": "削除失敗", "lines": [{"text": "削除失敗"}]},
                {"title": "削除成功", "lines": [{"text": "削除成功"}]},
            ],
            delete_errors={"削除失敗": RuntimeError("削除失敗")},
        )

        result = await MirrorService(source, destination, "", "").run()

        self.assertEqual(result.failed_pages, 1)
        self.assertEqual(result.deleted_pages, 1)
        self.assertEqual(result.failed_titles, ["削除失敗"])
        self.assertEqual(result.deleted_titles, ["削除成功"])
        self.assertEqual(destination.deleted_titles, ["削除失敗", "削除成功"])
        self.assertEqual(
            [page["title"] for page in destination.pages], ["削除失敗"]
        )


class _FakeCosenseClient:
    def __init__(
        self,
        pages,
        config_pages=None,
        tamper_after_import=False,
        config_error=None,
        delete_errors=None,
        export_error=None,
        import_error=None,
    ):
        self.pages = pages
        self.config_pages = config_pages or {}
        self.imported_pages = []
        self.deleted_titles = []
        self.export_calls = 0
        self.tamper_after_import = tamper_after_import
        self.config_error = config_error
        self.import_calls = 0
        self.fetch_page_lines_calls: dict[str, int] = {}
        self.delete_errors = delete_errors or {}
        self.export_error = export_error
        self.import_error = import_error

    async def export_pages(self):
        if self.export_error is not None:
            raise self.export_error
        self.export_calls += 1
        return self.pages

    async def fetch_page(self, title):
        return self.config_pages[title]

    async def fetch_page_lines(self, title):
        self.fetch_page_lines_calls[title] = self.fetch_page_lines_calls.get(title, 0) + 1
        if self.config_error is not None:
            raise self.config_error
        return [line["text"] for line in self.config_pages[title]["lines"]]

    async def import_pages(self, pages):
        if self.import_error is not None:
            raise self.import_error
        self.import_calls += 1
        self.imported_pages = copy.deepcopy(pages)
        imported_by_title = {page["title"]: copy.deepcopy(page) for page in pages}
        preserved = [
            page for page in self.pages if page.get("title") not in imported_by_title
        ]
        self.pages = preserved + list(imported_by_title.values())
        if self.tamper_after_import:
            self.pages[-1]["lines"][0]["text"] = "改ざんされた値"

    async def delete_page(self, title):
        self.deleted_titles.append(title)
        if title in self.delete_errors:
            raise self.delete_errors[title]
        self.pages = [page for page in self.pages if page.get("title") != title]


class _ConcurrencyTrackingClient(_FakeCosenseClient):
    def __init__(self, pages):
        super().__init__(pages)
        self.active_exports = 0
        self.max_concurrent_exports = 0

    async def export_pages(self):
        self.active_exports += 1
        self.max_concurrent_exports = max(
            self.max_concurrent_exports, self.active_exports
        )
        await asyncio.sleep(0)
        self.active_exports -= 1
        return await super().export_pages()


if __name__ == "__main__":
    unittest.main()
