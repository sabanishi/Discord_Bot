import json
import re
import time
from urllib.parse import quote, urlparse

import aiohttp


SEASON_LIST_PAGE = "戦術対抗戦_シーズン一覧"
INTERNAL_LINK_PATTERN = re.compile(r"\[([^\[\]]+)]")
ICON_PAGE_CREATED_TIMESTAMP = 1
ICON_PAGE_GENERATED_BY_LINE = " This page was auto generated."


class TargetPageParseError(ValueError):
    pass


class IconPageError(RuntimeError):
    pass


def build_icon_page_title(student_name: str) -> str:
    """正式な生徒名からScrapboxアイコンページ名を作る。"""
    student_name = student_name.strip()
    if not student_name:
        raise IconPageError("生徒名が空です")
    return f"!{student_name}"


def build_icon_page_import_data(student_name: str, image_url: str) -> dict:
    """Gyazo画像を表示するアイコンページのimportデータを作る。"""
    parsed_url = urlparse(image_url)
    if parsed_url.scheme != "https" or parsed_url.hostname != "i.gyazo.com":
        raise IconPageError("アイコンページにはGyazoの画像URLが必要です")

    title = build_icon_page_title(student_name)
    return {
        "pages": [
            {
                "title": title,
                "created": ICON_PAGE_CREATED_TIMESTAMP,
                "lines": [
                    {
                        "text": title,
                        "created": ICON_PAGE_CREATED_TIMESTAMP,
                    },
                    {
                        "text": f"[{image_url}]",
                        "created": ICON_PAGE_CREATED_TIMESTAMP,
                    },
                    {
                        "text": ICON_PAGE_GENERATED_BY_LINE,
                        "created": ICON_PAGE_CREATED_TIMESTAMP,
                    },
                    {
                        "text": "#戦術対抗戦_アイコン",
                        "created": ICON_PAGE_CREATED_TIMESTAMP,
                    },
                ],
            }
        ]
    }


def build_page_update_import_data(
    title: str,
    lines: list[str],
    created: int,
    original_lines: list[dict],
    updated_at: int,
) -> dict:
    """対象ページの全行を更新するpage-data importデータを作る。"""
    imported_lines = []
    for index, text in enumerate(lines):
        original = original_lines[index] if index < len(original_lines) else {}
        unchanged = original.get("text") == text
        line_created = original.get("created", updated_at)
        line_updated = original.get("updated", updated_at) if unchanged else updated_at
        imported_lines.append(
            {
                "text": text,
                "created": line_created,
                "updated": line_updated,
            }
        )
    return {
        "pages": [
            {
                "title": title,
                "created": created,
                "updated": updated_at,
                "lines": imported_lines,
            }
        ]
    }


def is_persistent_cosense_page(page_data: object) -> bool:
    """Cosenseのレスポンスが実際に保存されたページを表すか判定する。"""
    return isinstance(page_data, dict) and page_data.get("persistent") is True


def is_ready_icon_page(page_data: object) -> bool:
    """ページタイトル画像と戦術対抗戦タグが保存済みか判定する。"""
    if not is_persistent_cosense_page(page_data):
        return False
    if page_data.get("created") != ICON_PAGE_CREATED_TIMESTAMP:
        return False

    image_url = page_data.get("image")
    if not isinstance(image_url, str):
        return False
    parsed_image = urlparse(image_url)
    if parsed_image.scheme != "https" or parsed_image.hostname != "i.gyazo.com":
        return False

    lines = page_data.get("lines")
    if not isinstance(lines, list):
        return False
    has_tag = any(
        isinstance(line, dict) and line.get("text") == "#戦術対抗戦_アイコン"
        for line in lines
    )
    has_generated_by = any(
        isinstance(line, dict)
        and line.get("text") == ICON_PAGE_GENERATED_BY_LINE
        for line in lines
    )
    expected_image_url = image_url.removesuffix("/raw")
    has_matching_image = any(
        isinstance(line, dict)
        and line.get("text") == f"[{expected_image_url}]"
        for line in lines
    )
    return has_tag and has_generated_by and has_matching_image


def parse_target_page_titles(page_data: dict) -> list[str]:
    """シーズン一覧ページのAPIレスポンスから対象ページ名を抽出する。"""
    if isinstance(page_data.get("lines"), list):
        titles = _extract_links_from_lines(page_data.get("lines"))
    else:
        links = page_data.get("links")
        if not isinstance(links, list):
            raise TargetPageParseError("シーズン一覧ページの形式が不正です")
        titles = [link for link in links if isinstance(link, str)]

    unique_titles: list[str] = []
    seen: set[str] = set()
    for title in titles:
        title = title.strip()
        if not title or title == SEASON_LIST_PAGE or title in seen:
            continue
        seen.add(title)
        unique_titles.append(title)

    if not unique_titles:
        raise TargetPageParseError("対象の戦術対抗戦ページが登録されていません")

    return unique_titles


def _extract_links_from_lines(lines: object) -> list[str]:
    if not isinstance(lines, list):
        raise TargetPageParseError("シーズン一覧ページの形式が不正です")

    links: list[str] = []
    for line in lines:
        if not isinstance(line, dict):
            continue

        text = line.get("text")
        if isinstance(text, str):
            links.extend(INTERNAL_LINK_PATTERN.findall(text))

    return links


class TacticalChallengeCosenseClient:
    def __init__(
        self,
        project: str,
        sid: str,
        timeout_seconds: int = 30,
    ):
        self.project = project
        self.sid = self._normalize_sid(sid)
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def fetch_target_page_titles(self) -> list[str]:
        """Cosenseのシーズン一覧ページから処理対象ページを取得する。"""
        page_data = await self._fetch_page(SEASON_LIST_PAGE)
        return parse_target_page_titles(page_data)

    async def fetch_page(self, title: str) -> dict:
        """Cosenseから指定したページの全データを取得する。"""
        return await self._fetch_page(title)

    async def icon_page_exists(self, student_name: str) -> bool:
        """正式名称に対応するScrapboxアイコンページの存在を確認する。"""
        title = build_icon_page_title(student_name)
        encoded_project = quote(self.project, safe="")
        encoded_title = quote(title, safe="")
        url = f"https://scrapbox.io/api/pages/{encoded_project}/{encoded_title}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Cookie": f"connect.sid={self.sid}",
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, headers=headers) as response:
                response_text = await response.text()
                if response.status == 404:
                    return False
                if response.status < 200 or response.status >= 300:
                    raise IconPageError(
                        "Scrapboxアイコンページを確認できませんでした: "
                        f"status={response.status}, body={response_text[:500]}"
                    )
        try:
            page_data = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise IconPageError(
                "Scrapboxアイコンページが不正なJSONを返しました"
            ) from exc
        return is_ready_icon_page(page_data)

    async def fetch_icon_page(self, student_name: str) -> dict:
        """Scrapboxアイコンページを再取得して内容を返す。"""
        return await self._fetch_page(build_icon_page_title(student_name))

    async def ensure_icon_page(self, student_name: str, image_url: str) -> bool:
        """不足しているScrapboxアイコンページだけを作成する。"""
        if await self.icon_page_exists(student_name):
            return False

        import_data = build_icon_page_import_data(student_name, image_url)
        encoded_project = quote(self.project, safe="")
        url = f"https://scrapbox.io/api/page-data/import/{encoded_project}.json"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Cookie": f"connect.sid={self.sid}",
            "Origin": "https://scrapbox.io",
            "Referer": (
                f"https://scrapbox.io/{encoded_project}/settings/page-data"
            ),
        }
        form = aiohttp.FormData()
        form.add_field(
            "import-file",
            json.dumps(import_data, ensure_ascii=False).encode("utf-8"),
            filename="import.json",
            content_type="application/octet-stream",
        )

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, headers=headers, data=form) as response:
                response_text = await response.text()
                if response.status < 200 or response.status >= 300:
                    raise IconPageError(
                        "Scrapboxアイコンページを作成できませんでした: "
                        f"status={response.status}, body={response_text[:500]}"
                    )
        return True

    async def update_page_lines(
        self,
        title: str,
        lines: list[str],
        original_page: dict,
    ) -> None:
        """Cosenseの対象ページを指定した全行で更新する。"""
        import_data = build_page_update_import_data(
            title,
            lines,
            original_page["created"],
            original_page["lines"],
            int(time.time()),
        )
        encoded_project = quote(self.project, safe="")
        url = f"https://scrapbox.io/api/page-data/import/{encoded_project}.json"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Cookie": f"connect.sid={self.sid}",
            "Origin": "https://scrapbox.io",
            "Referer": (
                f"https://scrapbox.io/{encoded_project}/settings/page-data"
            ),
        }
        form = aiohttp.FormData()
        form.add_field(
            "import-file",
            json.dumps(import_data, ensure_ascii=False).encode("utf-8"),
            filename="import.json",
            content_type="application/octet-stream",
        )

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.post(url, headers=headers, data=form) as response:
                response_text = await response.text()
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(
                        "戦術対抗戦ページを更新できませんでした: "
                        f"status={response.status}, body={response_text[:500]}"
                    )

    async def _fetch_page(self, title: str) -> dict:
        encoded_project = quote(self.project, safe="")
        encoded_title = quote(title, safe="")
        url = f"https://scrapbox.io/api/pages/{encoded_project}/{encoded_title}"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Cookie": f"connect.sid={self.sid}",
        }

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            async with session.get(url, headers=headers) as response:
                response_text = await response.text()
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(
                        "戦術対抗戦の設定ページを取得できませんでした: "
                        f"status={response.status}, body={response_text[:500]}"
                    )

        try:
            page_data = json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "戦術対抗戦の設定ページが不正なJSONを返しました"
            ) from exc

        if not isinstance(page_data, dict):
            raise RuntimeError("戦術対抗戦の設定ページの形式が不正です")
        return page_data

    @staticmethod
    def _normalize_sid(sid: str) -> str:
        sid = sid.strip()
        if sid.startswith("connect.sid="):
            return sid.removeprefix("connect.sid=").strip()
        return sid
