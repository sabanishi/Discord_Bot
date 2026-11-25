import asyncio
import json
import unittest
from dataclasses import dataclass, field

from app.bookmark import (
    BookmarkCosenseClient,
    BookmarkRequest,
    BookmarkResult,
    BookmarkService,
    BookmarkTitleExistsError,
    PageMetadata,
    WebPageFetcher,
    build_bookmark_lines,
    extract_page_metadata,
    handle_bookmark_message,
    parse_bookmark_message,
)
from app.tactical_challenge.gyazo_client import GyazoUpload, GyazoUploadError


class ParseBookmarkMessageTests(unittest.TestCase):
    def test_url_only_message_has_empty_body(self):
        self.assertEqual(
            parse_bookmark_message("https://example.com/a"),
            BookmarkRequest(url="https://example.com/a", body_lines=[]),
        )

    def test_following_lines_are_kept_including_blank_lines(self):
        self.assertEqual(
            parse_bookmark_message("https://example.com/a\n\nほげほげ\n\nふがふが"),
            BookmarkRequest(
                url="https://example.com/a",
                body_lines=["", "ほげほげ", "", "ふがふが"],
            ),
        )

    def test_surrounding_spaces_on_first_line_are_ignored(self):
        self.assertEqual(
            parse_bookmark_message("  http://example.com/a  \nmemo"),
            BookmarkRequest(url="http://example.com/a", body_lines=["memo"]),
        )

    def test_messages_without_url_only_first_line_are_ignored(self):
        for content in [
            "",
            "ほげほげ",
            "これ良かった https://example.com/a",
            "https://example.com/a https://example.com/b",
            "memo\nhttps://example.com/a",
            "ftp://example.com/a",
        ]:
            with self.subTest(content=content):
                self.assertIsNone(parse_bookmark_message(content))


class ExtractPageMetadataTests(unittest.TestCase):
    def test_og_title_and_image_are_preferred(self):
        html = """
        <html><head>
        <title>タイトルタグ</title>
        <meta property="og:title" content="OGタイトル">
        <meta property="og:image" content="https://cdn.example.com/og.png">
        </head></html>
        """
        self.assertEqual(
            extract_page_metadata(html, "https://example.com/a"),
            PageMetadata(title="OGタイトル", image_url="https://cdn.example.com/og.png"),
        )

    def test_title_tag_is_used_without_og_title(self):
        html = "<html><head><title>\n  タイトル\n  タグ </title></head></html>"
        self.assertEqual(
            extract_page_metadata(html, "https://example.com/a"),
            PageMetadata(title="タイトル タグ", image_url=None),
        )

    def test_relative_og_image_is_resolved(self):
        html = '<meta property="og:image" content="/img/og.png">'
        self.assertEqual(
            extract_page_metadata(html, "https://example.com/dir/a"),
            PageMetadata(title=None, image_url="https://example.com/img/og.png"),
        )

    def test_blank_values_are_treated_as_missing(self):
        html = '<meta property="og:title" content="  "><title> </title><meta property="og:image" content="">'
        self.assertEqual(
            extract_page_metadata(html, "https://example.com/a"),
            PageMetadata(title=None, image_url=None),
        )


class BuildBookmarkLinesTests(unittest.TestCase):
    def test_lines_with_image_and_body(self):
        self.assertEqual(
            build_bookmark_lines(
                "記事", "https://gyazo.com/abc", "https://example.com/a",
                ["", "ほげほげ", "", "ふがふが"],
            ),
            [
                "記事",
                "[https://gyazo.com/abc]",
                "[https://example.com/a]",
                "",
                "ほげほげ",
                "",
                "ふがふが",
            ],
        )

    def test_image_line_is_omitted_without_image(self):
        self.assertEqual(
            build_bookmark_lines("記事", None, "https://example.com/a", []),
            ["記事", "[https://example.com/a]"],
        )


@dataclass
class FakeCosense:
    existing_titles: set[str] = field(default_factory=set)
    created: list[tuple[str, list[str]]] = field(default_factory=list)
    create_error: Exception | None = None

    def page_url(self, title: str) -> str:
        return f"https://scrapbox.io/project/{title}"

    async def page_exists(self, title: str) -> bool:
        return title in self.existing_titles

    async def create_page(self, title: str, lines: list[str]) -> str:
        if self.create_error is not None:
            raise self.create_error
        self.created.append((title, lines))
        self.existing_titles.add(title)
        return self.page_url(title)


@dataclass
class FakeGyazo:
    error: Exception | None = None
    uploaded: list[tuple[bytes, str]] = field(default_factory=list)

    async def upload_image(self, image: bytes, filename: str) -> GyazoUpload:
        if self.error is not None:
            raise self.error
        self.uploaded.append((image, filename))
        return GyazoUpload(
            image_id="abc",
            permalink_url="https://gyazo.com/abc",
            image_url="https://i.gyazo.com/abc.png",
        )


@dataclass
class FakeWeb:
    html: str | None = None
    images: dict[str, bytes] = field(default_factory=dict)
    fetched_images: list[str] = field(default_factory=list)

    async def fetch_html(self, url: str) -> str | None:
        return self.html

    async def fetch_image(self, url: str) -> bytes | None:
        self.fetched_images.append(url)
        return self.images.get(url)


@dataclass
class FakeAttachment:
    data: bytes = b"attached"
    filename: str = "photo.jpg"
    content_type: str | None = "image/jpeg"
    error: Exception | None = None

    async def read(self) -> bytes:
        if self.error is not None:
            raise self.error
        return self.data


OG_HTML = (
    '<meta property="og:title" content="記事タイトル">'
    '<meta property="og:image" content="https://example.com/og.png">'
)


class BookmarkServiceTests(unittest.TestCase):
    def run_service(self, cosense, gyazo, web, request, attachment=None):
        service = BookmarkService(cosense=cosense, gyazo=gyazo, web=web)
        return asyncio.run(service.create_bookmark(request, attachment))

    def test_creates_page_with_uploaded_og_image(self):
        cosense, gyazo = FakeCosense(), FakeGyazo()
        web = FakeWeb(html=OG_HTML, images={"https://example.com/og.png": b"og"})
        request = BookmarkRequest(url="https://example.com/a", body_lines=["", "ほげほげ"])

        result = self.run_service(cosense, gyazo, web, request)

        self.assertEqual(
            result,
            BookmarkResult(page_url="https://scrapbox.io/project/記事タイトル", image_error=None),
        )
        self.assertEqual(
            cosense.created,
            [(
                "記事タイトル",
                [
                    "記事タイトル",
                    "[https://gyazo.com/abc]",
                    "[https://example.com/a]",
                    "",
                    "ほげほげ",
                ],
            )],
        )
        self.assertEqual(gyazo.uploaded[0][0], b"og")

    def test_attached_image_takes_priority_over_og_image(self):
        cosense, gyazo = FakeCosense(), FakeGyazo()
        web = FakeWeb(html=OG_HTML, images={"https://example.com/og.png": b"og"})
        request = BookmarkRequest(url="https://example.com/a", body_lines=[])

        self.run_service(cosense, gyazo, web, request, FakeAttachment(data=b"attached"))

        self.assertEqual([image for image, _ in gyazo.uploaded], [b"attached"])
        self.assertEqual(web.fetched_images, [])
        self.assertEqual(cosense.created[0][1][1], "[https://gyazo.com/abc]")

    def test_url_is_used_as_title_when_page_cannot_be_fetched(self):
        cosense, gyazo, web = FakeCosense(), FakeGyazo(), FakeWeb(html=None)
        request = BookmarkRequest(url="https://example.com/a", body_lines=[])

        self.run_service(cosense, gyazo, web, request)

        self.assertEqual(
            cosense.created,
            [("https://example.com/a", ["https://example.com/a", "[https://example.com/a]"])],
        )
        self.assertEqual(gyazo.uploaded, [])

    def test_image_line_is_omitted_when_og_image_cannot_be_fetched(self):
        cosense, gyazo, web = FakeCosense(), FakeGyazo(), FakeWeb(html=OG_HTML)
        request = BookmarkRequest(url="https://example.com/a", body_lines=[])

        result = self.run_service(cosense, gyazo, web, request)

        self.assertIsNone(result.image_error)
        self.assertEqual(cosense.created[0][1], ["記事タイトル", "[https://example.com/a]"])

    def test_page_is_created_without_image_when_gyazo_upload_fails(self):
        cosense = FakeCosense()
        gyazo = FakeGyazo(error=GyazoUploadError("upload failed"))
        web = FakeWeb(html=OG_HTML, images={"https://example.com/og.png": b"og"})
        request = BookmarkRequest(url="https://example.com/a", body_lines=[])

        result = self.run_service(cosense, gyazo, web, request)

        self.assertIn("upload failed", result.image_error)
        self.assertEqual(cosense.created[0][1], ["記事タイトル", "[https://example.com/a]"])

    def test_page_is_created_without_image_when_attachment_cannot_be_read(self):
        cosense, gyazo = FakeCosense(), FakeGyazo()
        web = FakeWeb(html=OG_HTML, images={"https://example.com/og.png": b"og"})
        request = BookmarkRequest(url="https://example.com/a", body_lines=[])

        result = self.run_service(
            cosense, gyazo, web, request, FakeAttachment(error=RuntimeError("read failed"))
        )

        self.assertIn("read failed", result.image_error)
        self.assertEqual(gyazo.uploaded, [])
        self.assertEqual(cosense.created[0][1], ["記事タイトル", "[https://example.com/a]"])

    def test_existing_title_stops_creation(self):
        cosense = FakeCosense(existing_titles={"記事タイトル"})
        gyazo = FakeGyazo()
        web = FakeWeb(html=OG_HTML, images={"https://example.com/og.png": b"og"})
        request = BookmarkRequest(url="https://example.com/a", body_lines=[])

        with self.assertRaises(BookmarkTitleExistsError) as context:
            self.run_service(cosense, gyazo, web, request)

        self.assertEqual(context.exception.page_url, "https://scrapbox.io/project/記事タイトル")
        self.assertEqual(cosense.created, [])
        self.assertEqual(gyazo.uploaded, [])


class FakeResponse:
    def __init__(self, status: int, body: bytes = b"", content_type: str = "text/html"):
        self.status = status
        self.body = body
        self.headers = {"Content-Type": content_type}
        self.charset = "utf-8"

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return None

    async def text(self):
        return self.body.decode("utf-8")

    async def read(self):
        return self.body


class FakeSession:
    def __init__(self, responses: dict[tuple[str, str], FakeResponse]):
        self.responses = responses
        self.requests: list[dict] = []

    def _request(self, method, url, **kwargs):
        self.requests.append({"method": method, "url": url, **kwargs})
        response = self.responses.get((method, url))
        if response is None:
            raise AssertionError(f"unexpected request: {method} {url}")
        if isinstance(response, Exception):
            raise response
        return response

    def get(self, url, **kwargs):
        return self._request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self._request("POST", url, **kwargs)


class BookmarkCosenseClientTests(unittest.TestCase):
    PAGE_API = "https://scrapbox.io/api/pages/my%20project/a%2Fb"

    def test_page_exists_uses_persistent_flag(self):
        cases = [
            (FakeResponse(200, json.dumps({"persistent": True}).encode()), True),
            (FakeResponse(200, json.dumps({"persistent": False}).encode()), False),
            (FakeResponse(404, b"{}"), False),
        ]
        for response, expected in cases:
            with self.subTest(expected=expected, status=response.status):
                session = FakeSession({("GET", self.PAGE_API): response})
                client = BookmarkCosenseClient("my project", "connect.sid=sid", session)
                self.assertIs(asyncio.run(client.page_exists("a/b")), expected)
                self.assertEqual(session.requests[0]["headers"]["Cookie"], "connect.sid=sid")

    def test_page_exists_raises_on_server_error(self):
        session = FakeSession({("GET", self.PAGE_API): FakeResponse(500, b"error")})
        client = BookmarkCosenseClient("my project", "sid", session)
        with self.assertRaises(RuntimeError):
            asyncio.run(client.page_exists("a/b"))

    def test_create_page_posts_import_data_and_returns_url(self):
        import_url = "https://scrapbox.io/api/page-data/import/my%20project.json"
        session = FakeSession({("POST", import_url): FakeResponse(200, b"{}")})
        client = BookmarkCosenseClient("my project", "sid", session)

        page_url = asyncio.run(client.create_page("a/b", ["a/b", "[https://example.com]"]))

        self.assertEqual(page_url, "https://scrapbox.io/my%20project/a%2Fb")
        request = session.requests[0]
        self.assertEqual(request["headers"]["Origin"], "https://scrapbox.io")
        form = request["data"]
        field_value = form._fields[0][2]
        self.assertEqual(
            json.loads(field_value.decode("utf-8")),
            {"pages": [{"title": "a/b", "lines": ["a/b", "[https://example.com]"]}]},
        )

    def test_create_page_raises_on_error_status(self):
        import_url = "https://scrapbox.io/api/page-data/import/p.json"
        session = FakeSession({("POST", import_url): FakeResponse(403, b"forbidden")})
        client = BookmarkCosenseClient("p", "sid", session)
        with self.assertRaisesRegex(RuntimeError, "403"):
            asyncio.run(client.create_page("t", ["t"]))


class WebPageFetcherTests(unittest.TestCase):
    def test_fetch_html_returns_text_for_html(self):
        session = FakeSession({("GET", "https://example.com/a"): FakeResponse(200, "<title>t</title>".encode())})
        self.assertEqual(
            asyncio.run(WebPageFetcher(session).fetch_html("https://example.com/a")),
            "<title>t</title>",
        )

    def test_fetch_html_returns_none_for_failures(self):
        cases = [
            FakeResponse(404, b"not found"),
            FakeResponse(200, b"%PDF", content_type="application/pdf"),
            OSError("network"),
        ]
        for response in cases:
            with self.subTest(response=response):
                session = FakeSession({("GET", "https://example.com/a"): response})
                self.assertIsNone(asyncio.run(WebPageFetcher(session).fetch_html("https://example.com/a")))

    def test_fetch_image_returns_bytes_only_for_images(self):
        url = "https://example.com/og.png"
        ok = FakeSession({("GET", url): FakeResponse(200, b"png", content_type="image/png")})
        self.assertEqual(asyncio.run(WebPageFetcher(ok).fetch_image(url)), b"png")
        not_image = FakeSession({("GET", url): FakeResponse(200, b"<html>", content_type="text/html")})
        self.assertIsNone(asyncio.run(WebPageFetcher(not_image).fetch_image(url)))
        failed = FakeSession({("GET", url): FakeResponse(500, b"")})
        self.assertIsNone(asyncio.run(WebPageFetcher(failed).fetch_image(url)))


@dataclass
class FakeMessage:
    content: str
    attachments: list = field(default_factory=list)
    replies: list[str] = field(default_factory=list)
    reactions: list[str] = field(default_factory=list)
    reaction_error: Exception | None = None

    async def reply(self, text: str) -> None:
        self.replies.append(text)

    async def add_reaction(self, emoji: str) -> None:
        if self.reaction_error is not None:
            raise self.reaction_error
        self.reactions.append(emoji)


@dataclass
class FakeNotifier:
    sent: list[tuple[int, str]] = field(default_factory=list)

    async def send(self, channel_id: int, message: str) -> bool:
        self.sent.append((channel_id, message))
        return True


@dataclass
class FakeService:
    result: BookmarkResult | None = None
    error: Exception | None = None
    calls: list = field(default_factory=list)

    message: "FakeMessage | None" = None
    reactions_at_call: list[str] | None = None

    async def create_bookmark(self, request, attachment):
        self.calls.append((request, attachment))
        if self.message is not None:
            self.reactions_at_call = list(self.message.reactions)
        if self.error is not None:
            raise self.error
        return self.result


class HandleBookmarkMessageTests(unittest.TestCase):
    def handle(self, message, service, notifier):
        asyncio.run(handle_bookmark_message(message, service, notifier, alert_channel_id=99))

    def test_non_url_message_is_ignored(self):
        message, service, notifier = FakeMessage("ほげ"), FakeService(), FakeNotifier()
        self.handle(message, service, notifier)
        self.assertEqual(service.calls, [])
        self.assertEqual(message.replies, [])
        self.assertEqual(message.reactions, [])
        self.assertEqual(notifier.sent, [])

    def test_thumbs_up_is_added_before_processing(self):
        message = FakeMessage("https://example.com/a")
        service = FakeService(
            result=BookmarkResult(page_url="https://scrapbox.io/p/t", image_error=None),
            message=message,
        )

        self.handle(message, service, FakeNotifier())

        self.assertEqual(service.reactions_at_call, ["\N{THUMBS UP SIGN}"])
        self.assertEqual(message.reactions, ["\N{THUMBS UP SIGN}"])

    def test_processing_continues_when_reaction_fails(self):
        message = FakeMessage("https://example.com/a", reaction_error=RuntimeError("forbidden"))
        service = FakeService(
            result=BookmarkResult(page_url="https://scrapbox.io/p/t", image_error=None)
        )

        self.handle(message, service, FakeNotifier())

        self.assertEqual(len(service.calls), 1)
        self.assertIn("https://scrapbox.io/p/t", message.replies[0])

    def test_success_replies_with_page_url_and_uses_first_image_attachment(self):
        first, second = FakeAttachment(filename="1.png"), FakeAttachment(filename="2.png")
        text_file = FakeAttachment(filename="memo.txt", content_type="text/plain")
        message = FakeMessage("https://example.com/a\nmemo", attachments=[text_file, first, second])
        service = FakeService(result=BookmarkResult(page_url="https://scrapbox.io/p/t", image_error=None))
        notifier = FakeNotifier()

        self.handle(message, service, notifier)

        self.assertEqual(
            service.calls,
            [(BookmarkRequest(url="https://example.com/a", body_lines=["memo"]), first)],
        )
        self.assertEqual(
            message.replies,
            [
                "ブックマーク、保存しておきました。\n"
                "https://scrapbox.io/p/t\n"
                "……後でちゃんと読み返してくださいね。保存しただけで満足するのは禁止です。"
            ],
        )
        self.assertEqual(notifier.sent, [])

    def test_image_failure_is_reported_in_reply(self):
        message = FakeMessage("https://example.com/a")
        service = FakeService(result=BookmarkResult(page_url="https://scrapbox.io/p/t", image_error="upload failed"))
        notifier = FakeNotifier()

        self.handle(message, service, notifier)

        self.assertIsNone(service.calls[0][1])
        self.assertEqual(
            message.replies,
            [
                "ページは作成しました。\n"
                "https://scrapbox.io/p/t\n"
                "ただ、画像はGyazoにアップロードできなかったので外してあります。"
                "……私の不手際ではありませんからね。\n"
                "原因: upload failed"
            ],
        )
        self.assertEqual(notifier.sent, [])

    def test_existing_title_is_reported_in_reply(self):
        message = FakeMessage("https://example.com/a")
        service = FakeService(error=BookmarkTitleExistsError("https://scrapbox.io/p/t"))
        notifier = FakeNotifier()

        self.handle(message, service, notifier)

        self.assertEqual(
            message.replies,
            [
                "同じタイトルのページがもうありますよ。"
                "二重に作っても散らかるだけなので、今回は作成しませんでした。\n"
                "https://scrapbox.io/p/t"
            ],
        )
        self.assertEqual(notifier.sent, [])

    def test_creation_failure_is_reported_to_reply_and_alert_channel(self):
        message = FakeMessage("https://example.com/a")
        service = FakeService(error=RuntimeError("import failed"))
        notifier = FakeNotifier()

        self.handle(message, service, notifier)

        self.assertEqual(
            message.replies,
            [
                "……ページを作成できませんでした。詳しい状況は警告チャンネルに報告しておきます。\n"
                "原因: import failed"
            ],
        )
        self.assertEqual(
            notifier.sent,
            [(
                99,
                "ブックマークページの作成に失敗しました。確認をお願いします。\n"
                "URL: https://example.com/a\n"
                "原因: import failed",
            )],
        )


if __name__ == "__main__":
    unittest.main()
