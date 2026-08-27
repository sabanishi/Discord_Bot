import aiohttp
from urllib.parse import urlparse

from .wiki_parser import parse_student_icons
from .wiki_types import StudentIcon


WIKI_BASE_URL = "https://bluearchive.wikiru.jp/"
CHARACTER_ICON_TABLE_URL = (
    "https://bluearchive.wikiru.jp/"
    "?%E3%83%86%E3%83%BC%E3%83%96%E3%83%AB%2F"
    "%E3%82%AD%E3%83%A3%E3%83%A9%E3%82%A2%E3%82%A4%E3%82%B3%E3%83%B3"
)


class BlueArchiveWikiClient:
    def __init__(self, timeout_seconds: int = 30):
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.headers = {"User-Agent": "Discord_Bot/1.0 (character icon fetcher)"}

    async def fetch_student_icons(self) -> list[StudentIcon]:
        """攻略Wikiから生徒の正式名称とアイコンURLの一覧を取得する。"""
        async with aiohttp.ClientSession(
            timeout=self.timeout,
            headers=self.headers,
        ) as session:
            async with session.get(CHARACTER_ICON_TABLE_URL) as response:
                html = await response.text()
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(
                        "攻略Wikiのキャラアイコン表を取得できませんでした: "
                        f"status={response.status}, body={html[:500]}"
                    )

        return parse_student_icons(html, WIKI_BASE_URL)

    async def fetch_icon_image(self, image_url: str) -> bytes:
        """攻略Wiki内のアイコン画像をダウンロードする。"""
        parsed_url = urlparse(image_url)
        if parsed_url.scheme != "https" or parsed_url.hostname != "bluearchive.wikiru.jp":
            raise ValueError("攻略Wiki以外の画像URLは取得できません")

        async with aiohttp.ClientSession(
            timeout=self.timeout,
            headers=self.headers,
        ) as session:
            async with session.get(image_url) as response:
                image = await response.read()
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(
                        "攻略Wikiのキャラアイコン画像を取得できませんでした: "
                        f"status={response.status}"
                    )

                content_type = response.headers.get("Content-Type", "")
                if not content_type.lower().startswith("image/"):
                    raise RuntimeError(
                        "攻略Wikiが画像以外のデータを返しました: "
                        f"content_type={content_type}"
                    )
                if not image:
                    raise RuntimeError("攻略Wikiが空の画像を返しました")

        return image
