import asyncio
import json
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app.diary import DiaryClient, build_page_from_template, normalize_lines


class DiaryServiceTests(unittest.TestCase):
    def test_build_page_from_template_expands_relative_dates(self):
        title, lines = build_page_from_template(
            datetime(2026, 10, 1),
            Path(__file__).resolve().parents[2] / "template.txt",
        )

        self.assertEqual(title, "2026-10-01")
        self.assertTrue(any("2026-09-30" in line for line in lines))
        self.assertTrue(any("2026-10-02" in line for line in lines))

    def test_normalize_lines_removes_only_trailing_empty_lines(self):
        self.assertEqual(
            normalize_lines(["a", "", "b", "", ""]),
            ["a", "", "b"],
        )

    def test_template_without_title_is_rejected(self):
        template = Path(__file__).resolve().parent / "empty_template.txt"
        template.write_text("\nbody\n", encoding="utf-8")
        self.addCleanup(template.unlink)

        with self.assertRaisesRegex(ValueError, "1行目"):
            build_page_from_template(datetime(2026, 10, 1), template)

    def test_diary_client_normalizes_sid_and_builds_page_url(self):
        client = DiaryClient("project name", "connect.sid=session")

        self.assertEqual(client.sid, "session")
        self.assertEqual(
            client.page_url("2026-10-01"),
            "https://scrapbox.io/project%20name/2026-10-01",
        )

    def test_diary_client_uses_injected_session_without_closing_it(self):
        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            def get(self, url, headers):
                return Response()

        class Response:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def text(self):
                return '{"lines": [{"text": "saved"}]}'

        session = Session()
        with patch("app.diary.aiohttp.ClientSession") as session_factory:
            lines = asyncio.run(DiaryClient("project", "sid", session).fetch_page_lines("page"))

        self.assertEqual(lines, ["saved"])
        session_factory.assert_not_called()

    def test_diary_client_fetches_saved_lines_from_response(self):
        class Response:
            status = 200

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def text(self):
                return '{"lines": [{"text": "saved"}, {"text": ""}]}'

        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            def get(self, url, headers):
                self.url = url
                self.headers = headers
                return Response()

        with patch("app.diary.aiohttp.ClientSession", return_value=Session()):
            lines = asyncio.run(DiaryClient("project", "sid").fetch_page_lines("page"))

        self.assertEqual(lines, ["saved", ""])

    def test_diary_client_rejects_missing_page(self):
        class Response:
            status = 404

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def text(self):
                return "not found"

        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            def get(self, url, headers):
                return Response()

        with patch("app.diary.aiohttp.ClientSession", return_value=Session()):
            with self.assertRaisesRegex(RuntimeError, "ページが見つかりません"):
                asyncio.run(DiaryClient("project", "sid").fetch_page_lines("page"))

    def test_diary_client_creates_page_with_expected_request_and_reloads_lines(self):
        calls = []

        class Response:
            status = 200

            def __init__(self, body):
                self.body = body

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def text(self):
                return self.body

        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            def post(self, url, headers, data):
                calls.append(("post", url, headers, data))
                return Response("{}")

            def get(self, url, headers):
                calls.append(("get", url, headers))
                return Response('{"lines": [{"text": "saved title"}, {"text": "saved body"}]}')

        client = DiaryClient("project", "connect.sid=session")
        with patch("app.diary.aiohttp.ClientSession", return_value=Session()):
            page_url = asyncio.run(client.create_page("page", ["page", "body"]))
            saved_lines = asyncio.run(client.fetch_page_lines("page"))

        self.assertEqual(page_url, "https://scrapbox.io/project/page")
        self.assertEqual(saved_lines, ["saved title", "saved body"])
        self.assertEqual(calls[0][0], "post")
        self.assertEqual(calls[0][1], "https://scrapbox.io/api/page-data/import/project.json")
        self.assertEqual(calls[0][2]["Cookie"], "connect.sid=session")
        payload = json.loads(calls[0][3]._fields[0][2].decode("utf-8"))
        self.assertEqual(payload, {"pages": [{"title": "page", "lines": ["page", "body"]}]})
        self.assertEqual(calls[1][0], "get")

    def test_diary_client_rejects_server_error(self):
        class Response:
            status = 500

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def text(self):
                return "server error"

        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            def get(self, url, headers):
                return Response()

        with patch("app.diary.aiohttp.ClientSession", return_value=Session()):
            with self.assertRaisesRegex(RuntimeError, "status=500"):
                asyncio.run(DiaryClient("project", "sid").fetch_page_lines("page"))

    def test_diary_client_rejects_create_server_error(self):
        class Response:
            status = 503

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            async def text(self):
                return "unavailable"

        class Session:
            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return None

            def post(self, url, headers, data):
                return Response()

        with patch("app.diary.aiohttp.ClientSession", return_value=Session()):
            with self.assertRaisesRegex(RuntimeError, "status=503"):
                asyncio.run(DiaryClient("project", "sid").create_page("page", ["page"]))

    def test_diary_client_rejects_invalid_json_and_missing_lines(self):
        for body, expected in [
            ("not json", "JSONDecodeError"),
            ('{"page": {}}', "結果が不正"),
            ('{"lines": "invalid"}', "結果が不正"),
        ]:
            class Response:
                status = 200

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return None

                async def text(self):
                    return body

            class Session:
                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return None

                def get(self, url, headers):
                    return Response()

            with self.subTest(expected=expected):
                with patch("app.diary.aiohttp.ClientSession", return_value=Session()):
                    if expected == "JSONDecodeError":
                        with self.assertRaises(json.JSONDecodeError):
                            asyncio.run(DiaryClient("project", "sid").fetch_page_lines("page"))
                    elif expected == "結果が不正":
                        with self.assertRaisesRegex(RuntimeError, expected):
                            asyncio.run(DiaryClient("project", "sid").fetch_page_lines("page"))
                    else:
                        with self.assertRaisesRegex(RuntimeError, "行"):
                            asyncio.run(DiaryClient("project", "sid").fetch_page_lines("page"))


if __name__ == "__main__":
    unittest.main()
