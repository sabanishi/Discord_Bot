import json
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import quote, urljoin, urlparse

import aiohttp

from app.notifications import DiscordNotifier
from app.tactical_challenge.gyazo_client import GyazoClient, GyazoUpload


USER_AGENT = "Mozilla/5.0 (compatible; ScrapboxBookmarkBot/1.0)"
FETCH_TIMEOUT = aiohttp.ClientTimeout(total=20)
RECEIVED_REACTION = "\N{THUMBS UP SIGN}"


@dataclass(frozen=True)
class BookmarkRequest:
    url: str
    body_lines: list[str]


@dataclass(frozen=True)
class PageMetadata:
    title: str | None
    image_url: str | None


@dataclass(frozen=True)
class BookmarkResult:
    page_url: str
    image_error: str | None


class BookmarkTitleExistsError(RuntimeError):
    def __init__(self, page_url: str):
        super().__init__(f"同名のページが既に存在します: {page_url}")
        self.page_url = page_url


class ImageAttachment(Protocol):
    filename: str
    content_type: str | None

    async def read(self) -> bytes: ...


class BookmarkMessage(Protocol):
    content: str
    attachments: list[ImageAttachment]

    async def reply(self, content: str) -> object: ...

    async def add_reaction(self, emoji: str) -> None: ...


class BookmarkCosense(Protocol):
    def page_url(self, title: str) -> str: ...

    async def page_exists(self, title: str) -> bool: ...

    async def create_page(self, title: str, lines: list[str]) -> str: ...


class ImageUploader(Protocol):
    async def upload_image(self, image: bytes, filename: str) -> GyazoUpload: ...


class WebFetcher(Protocol):
    async def fetch_html(self, url: str) -> str | None: ...

    async def fetch_image(self, url: str) -> bytes | None: ...


class BookmarkCreator(Protocol):
    async def create_bookmark(
        self, request: BookmarkRequest, attachment: ImageAttachment | None
    ) -> BookmarkResult: ...


def _is_http_url(text: str) -> bool:
    if not text or re.search(r"\s", text):
        return False
    parsed = urlparse(text)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def parse_bookmark_message(content: str) -> BookmarkRequest | None:
    lines = content.split("\n")
    url = lines[0].strip()
    if not _is_http_url(url):
        return None
    return BookmarkRequest(url=url, body_lines=lines[1:])


def _normalize_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized or None


class _MetadataParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.og_title: str | None = None
        self.og_image: str | None = None
        self.title_parts: list[str] = []
        self.in_title = False
        self.title_found = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value for name, value in attrs}
        if tag == "meta":
            prop = (attributes.get("property") or attributes.get("name") or "").lower()
            content = attributes.get("content")
            if prop == "og:title" and self.og_title is None:
                self.og_title = _normalize_text(content)
            elif prop == "og:image" and self.og_image is None:
                self.og_image = (content or "").strip() or None
        elif tag == "title" and not self.title_found:
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title" and self.in_title:
            self.in_title = False
            self.title_found = True

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data)


def extract_page_metadata(html: str, base_url: str) -> PageMetadata:
    parser = _MetadataParser()
    parser.feed(html)
    parser.close()
    title = parser.og_title or _normalize_text("".join(parser.title_parts))
    image_url = urljoin(base_url, parser.og_image) if parser.og_image else None
    return PageMetadata(title=title, image_url=image_url)


def build_bookmark_lines(
    title: str, image_permalink: str | None, url: str, body_lines: list[str]
) -> list[str]:
    lines = [title]
    if image_permalink:
        lines.append(f"[{image_permalink}]")
    lines.append(f"[{url}]")
    lines.extend(body_lines)
    return lines


class WebPageFetcher:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def _get(self, url: str, content_type_prefix: str) -> bytes | None:
        try:
            async with self.session.get(
                url,
                headers={"User-Agent": USER_AGENT},
                timeout=FETCH_TIMEOUT,
                allow_redirects=True,
            ) as response:
                if response.status < 200 or response.status >= 300:
                    return None
                content_type = response.headers.get("Content-Type", "").lower()
                if not content_type.startswith(content_type_prefix):
                    return None
                return await response.read()
        except Exception as error:
            print(f"Webページの取得に失敗しました:\n{url}\n{error}", flush=True)
            return None

    async def fetch_html(self, url: str) -> str | None:
        body = await self._get(url, "text/html")
        if body is None:
            return None
        return body.decode("utf-8", errors="replace")

    async def fetch_image(self, url: str) -> bytes | None:
        return await self._get(url, "image/")


class BookmarkCosenseClient:
    def __init__(self, project: str, sid: str, session: aiohttp.ClientSession):
        self.project = project
        self.sid = sid.removeprefix("connect.sid=").strip()
        self.session = session

    @property
    def encoded_project(self) -> str:
        return quote(self.project, safe="")

    def page_url(self, title: str) -> str:
        return f"https://scrapbox.io/{self.encoded_project}/{quote(title, safe='')}"

    def _read_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Cookie": f"connect.sid={self.sid}",
        }

    async def page_exists(self, title: str) -> bool:
        url = (
            f"https://scrapbox.io/api/pages/{self.encoded_project}/"
            f"{quote(title, safe='')}"
        )
        async with self.session.get(url, headers=self._read_headers()) as response:
            response_text = await response.text()
            if response.status == 404:
                return False
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(
                    "Scrapboxページの存在確認に失敗しました:\n"
                    f"status={response.status}, body={response_text[:500]}"
                )
        data = json.loads(response_text)
        return data.get("persistent") is True

    async def create_page(self, title: str, lines: list[str]) -> str:
        url = f"https://scrapbox.io/api/page-data/import/{self.encoded_project}.json"
        form = aiohttp.FormData()
        form.add_field(
            "import-file",
            json.dumps(
                {"pages": [{"title": title, "lines": lines}]}, ensure_ascii=False
            ).encode("utf-8"),
            filename="import.json",
            content_type="application/octet-stream",
        )
        headers = {
            **self._read_headers(),
            "Origin": "https://scrapbox.io",
            "Referer": f"https://scrapbox.io/{self.encoded_project}/settings/page-data",
        }
        async with self.session.post(url, headers=headers, data=form) as response:
            response_text = await response.text()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(
                    "Scrapboxページ作成に失敗しました:\n"
                    f"status={response.status}, body={response_text[:500]}"
                )
        return self.page_url(title)


def _image_filename(url: str) -> str:
    name = urlparse(url).path.rsplit("/", 1)[-1]
    return name or "image"


class BookmarkService:
    def __init__(self, cosense: BookmarkCosense, gyazo: ImageUploader, web: WebFetcher):
        self.cosense = cosense
        self.gyazo = gyazo
        self.web = web

    async def create_bookmark(
        self, request: BookmarkRequest, attachment: ImageAttachment | None
    ) -> BookmarkResult:
        html = await self.web.fetch_html(request.url)
        metadata = (
            extract_page_metadata(html, request.url)
            if html is not None
            else PageMetadata(title=None, image_url=None)
        )
        title = metadata.title or request.url

        if await self.cosense.page_exists(title):
            raise BookmarkTitleExistsError(self.cosense.page_url(title))

        image_permalink, image_error = await self._upload_image(metadata, attachment)
        lines = build_bookmark_lines(title, image_permalink, request.url, request.body_lines)
        page_url = await self.cosense.create_page(title, lines)
        return BookmarkResult(page_url=page_url, image_error=image_error)

    async def _upload_image(
        self, metadata: PageMetadata, attachment: ImageAttachment | None
    ) -> tuple[str | None, str | None]:
        # 添付画像の読込失敗とGyazo失敗は通知対象、OGP画像の取得失敗は画像なしとして扱う
        try:
            if attachment is not None:
                image = await attachment.read()
                filename = attachment.filename
            elif metadata.image_url is not None:
                image = await self.web.fetch_image(metadata.image_url)
                if image is None:
                    return None, None
                filename = _image_filename(metadata.image_url)
            else:
                return None, None
            upload = await self.gyazo.upload_image(image, filename)
        except Exception as error:
            print(f"ブックマーク画像の処理に失敗しました:\n{error}", flush=True)
            return None, str(error)
        return upload.permalink_url, None


def build_bookmark_service(
    project: str, sid: str, gyazo_access_token: str, session: aiohttp.ClientSession
) -> BookmarkService:
    return BookmarkService(
        cosense=BookmarkCosenseClient(project, sid, session),
        gyazo=GyazoClient(gyazo_access_token, session=session),
        web=WebPageFetcher(session),
    )


def _first_image_attachment(attachments: list[ImageAttachment]) -> ImageAttachment | None:
    for attachment in attachments:
        if (attachment.content_type or "").startswith("image/"):
            return attachment
    return None


async def _reply(message: BookmarkMessage, text: str) -> None:
    try:
        await message.reply(text)
    except Exception as error:
        print(f"ブックマーク結果の返信に失敗しました:\n{error}", flush=True)


async def handle_bookmark_message(
    message: BookmarkMessage,
    service: BookmarkCreator,
    notifier: DiscordNotifier,
    alert_channel_id: int,
) -> None:
    request = parse_bookmark_message(message.content)
    if request is None:
        return

    try:
        await message.add_reaction(RECEIVED_REACTION)
    except Exception as error:
        print(f"受付リアクションの追加に失敗しました:\n{error}", flush=True)

    attachment = _first_image_attachment(list(message.attachments))
    try:
        result = await service.create_bookmark(request, attachment)
    except BookmarkTitleExistsError as error:
        await _reply(
            message,
            "同じタイトルのページがもうありますよ。\n"
            f"{error.page_url}",
        )
        return
    except Exception as error:
        print(f"ブックマークページの作成に失敗しました:\n{error}", flush=True)
        await _reply(
            message,
            "ページを作成できませんでした。詳しい状況は警告チャンネルに報告しておきますね。\n"
            f"{error}",
        )
        await notifier.send(
            alert_channel_id,
            "ブックマークページの作成に失敗しましたよ！ちゃんと確認してください。\n"
            f"URL: {request.url}\n"
            f"{error}",
        )
        return

    if result.image_error is None:
        text = (
            "ブックマーク、ちゃんと保存できましたよ(ﾌﾌﾝ\n"
            f"{result.page_url}\n"
        )
    else:
        text = (
            "ページは作成しました。\n"
            f"{result.page_url}\n"
            "ただ、画像はGyazoにアップロードできなかったので外してあります。"
            f"{result.image_error}"
        )
    await _reply(message, text)
