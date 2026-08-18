import re
from dataclasses import dataclass
from urllib.parse import quote

import aiohttp


@dataclass(frozen=True)
class PageSummary:
    page_id: str
    title: str
    linked_count: int


class LinkWarningState:
    def __init__(self, warning_threshold: int, resolve_threshold: int):
        if warning_threshold <= 0:
            raise ValueError("warning_threshold must be greater than zero")
        if resolve_threshold < 0 or resolve_threshold >= warning_threshold:
            raise ValueError("resolve_threshold must be between zero and warning_threshold")

        self.warning_threshold = warning_threshold
        self.resolve_threshold = resolve_threshold
        self.initialized = False
        self.warned_page_ids: set[str] = set()

    def find_new_warnings(
        self,
        pages: list[PageSummary],
        excluded_titles: set[str],
    ) -> list[PageSummary]:
        if not self.initialized:
            self.warned_page_ids = {
                page.page_id
                for page in pages
                if page.title not in excluded_titles
                and page.linked_count >= self.warning_threshold
            }
            self.initialized = True
            return []

        candidates: list[PageSummary] = []

        for page in pages:
            if page.title in excluded_titles:
                continue

            if page.page_id in self.warned_page_ids:
                if page.linked_count <= self.resolve_threshold:
                    self.warned_page_ids.remove(page.page_id)
                continue

            if page.linked_count >= self.warning_threshold:
                candidates.append(page)

        return candidates

    def mark_warned(self, page_id: str) -> None:
        self.warned_page_ids.add(page_id)


class ScrapboxLinkClient:
    def __init__(self, project: str, sid: str, timeout_seconds: int = 30):
        self.project = project
        self.sid = sid
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Cookie": f"connect.sid={self.sid}",
        }

    async def fetch_page_summaries(self) -> list[PageSummary]:
        encoded_project = quote(self.project, safe="")
        url = f"https://scrapbox.io/api/pages/{encoded_project}"
        limit = 1000
        skip = 0
        pages: list[PageSummary] = []

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            while True:
                data = await self._get_json(
                    session,
                    url,
                    params={"limit": limit, "skip": skip},
                )
                raw_pages = data.get("pages")
                total_count = data.get("count")

                if not isinstance(raw_pages, list) or not isinstance(total_count, int):
                    raise RuntimeError("Scrapboxページ一覧のレスポンス形式が不正です")

                for raw_page in raw_pages:
                    try:
                        page_id = raw_page["id"]
                        title = raw_page["title"]
                        linked_count = raw_page["linked"]
                    except (KeyError, TypeError) as exc:
                        raise RuntimeError("Scrapboxページ一覧に必須項目がありません") from exc

                    if (
                        not isinstance(page_id, str)
                        or not isinstance(title, str)
                        or not isinstance(linked_count, int)
                    ):
                        raise RuntimeError("Scrapboxページ一覧の項目形式が不正です")

                    pages.append(PageSummary(page_id, title, linked_count))

                skip += len(raw_pages)
                if not raw_pages or skip >= total_count:
                    break

        return pages

    async def fetch_excluded_titles(self, config_page_title: str) -> set[str]:
        if not config_page_title:
            return set()

        encoded_project = quote(self.project, safe="")
        encoded_title = quote(config_page_title, safe="")
        url = f"https://scrapbox.io/api/pages/{encoded_project}/{encoded_title}"

        async with aiohttp.ClientSession(timeout=self.timeout) as session:
            data = await self._get_json(session, url)

        page_links = data.get("links")
        if isinstance(page_links, list):
            return {
                config_page_title,
                *(link for link in page_links if isinstance(link, str)),
            }

        lines = data.get("lines")
        if not isinstance(lines, list):
            raise RuntimeError("Scrapbox除外設定ページのレスポンス形式が不正です")

        excluded: set[str] = {config_page_title}
        for line in lines:
            if not isinstance(line, dict):
                continue

            links = line.get("links")
            if isinstance(links, list):
                excluded.update(link for link in links if isinstance(link, str))
                continue

            text = line.get("text")
            if isinstance(text, str):
                excluded.update(extract_setting_links(text))

        return excluded

    async def _get_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: dict | None = None,
    ) -> dict:
        async with session.get(url, headers=self.headers, params=params) as response:
            response_text = await response.text()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(
                    f"Scrapbox APIの取得に失敗しました: "
                    f"status={response.status}, body={response_text[:500]}"
                )

            try:
                data = await response.json(content_type=None)
            except (ValueError, aiohttp.ContentTypeError) as exc:
                raise RuntimeError("Scrapbox APIが不正なJSONを返しました") from exc

        if not isinstance(data, dict):
            raise RuntimeError("Scrapbox APIのレスポンス形式が不正です")
        return data


BRACKET_LINK_PATTERN = re.compile(r"\[([^\[\]]+)]")
HASHTAG_PATTERN = re.compile(r"(?<!\S)#([^\s#]+)")


def extract_setting_links(text: str) -> set[str]:
    links = set(HASHTAG_PATTERN.findall(text))

    for content in BRACKET_LINK_PATTERN.findall(text):
        content = content.strip()
        if content and not content.startswith(("http://", "https://")):
            links.add(content)

    return links
