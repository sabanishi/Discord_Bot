from __future__ import annotations

import asyncio
import copy
import json
import re
from typing import TypeAlias
from urllib.parse import quote

import aiohttp


JsonPrimitive: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonPrimitive | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject: TypeAlias = dict[str, JsonValue]

DEFAULT_EXCLUDED_TAGS = {"#diary", "#研究"}
DEFAULT_EXCLUDED_ICONS = {"[private.icon]"}

INTERNAL_LINK_PATTERN = re.compile(r"\[([^\[\]]+)\]")
ATTACHMENT_REFERENCE_PATTERN = re.compile(
    r".+\.(?:apng|avif|gif|jpeg|jpg|mov|mp3|mp4|pdf|png|svg|webm|webp|zip)$",
    re.IGNORECASE,
)
HASHTAG_PATTERN = re.compile(r"(?<!\S)#[^\s#]+")


def build_page_data_export_url(project: str) -> str:
    encoded_project = quote(project, safe="")
    return (
        f"https://scrapbox.io/api/page-data/export/"
        f"{encoded_project}.json?metadata=true"
    )


def build_import_data(pages: list[JsonObject]) -> JsonObject:
    return {"pages": copy.deepcopy(pages)}


class MirrorCosenseClient:
    def __init__(
        self,
        project: str,
        sid: str,
        timeout_seconds: int = 30,
        session: aiohttp.ClientSession | None = None,
    ):
        self.project = project
        self.sid = sid.removeprefix("connect.sid=").strip()
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.session = session

    def _session_context(self):
        if self.session is not None:
            return _ExistingSessionContext(self.session)
        return aiohttp.ClientSession(timeout=self.timeout)

    @property
    def encoded_project(self) -> str:
        return quote(self.project, safe="")

    def _read_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json, text/plain, */*",
            "Cookie": f"connect.sid={self.sid}",
        }

    def _import_headers(self) -> dict[str, str]:
        return {
            **self._read_headers(),
            "Origin": "https://scrapbox.io",
            "Referer": (
                f"https://scrapbox.io/{self.encoded_project}/settings/page-data"
            ),
        }

    @staticmethod
    def _import_form(import_data: JsonObject) -> aiohttp.FormData:
        form = aiohttp.FormData()
        form.add_field(
            "import-file",
            json.dumps(import_data, ensure_ascii=False).encode("utf-8"),
            filename="import.json",
            content_type="application/octet-stream",
        )
        return form

    async def export_pages(self) -> list[JsonObject]:
        async with self._session_context() as session:
            data = await self._get_json(session, build_page_data_export_url(self.project))
        pages = data.get("pages")
        if not isinstance(pages, list) or not all(isinstance(page, dict) for page in pages):
            raise RuntimeError("Scrapboxエクスポート結果のpagesが不正です")
        for page in pages:
            if not isinstance(page.get("title"), str) or not page["title"]:
                raise RuntimeError("Scrapboxエクスポート結果の必須項目が不正です")
            if not isinstance(page.get("lines"), list):
                raise RuntimeError("Scrapboxエクスポート結果の必須項目が不正です")
        return pages

    async def fetch_page(self, title: str) -> JsonObject:
        encoded_title = quote(title, safe="")
        url = f"https://scrapbox.io/api/pages/{self.encoded_project}/{encoded_title}"
        async with self._session_context() as session:
            return await self._get_json(session, url)

    async def fetch_page_lines(self, title: str) -> list[str]:
        page = await self.fetch_page(title)
        raw_lines = page.get("lines")
        if not isinstance(raw_lines, list):
            raise RuntimeError(f"設定ページのlinesが不正です: {title}")
        lines: list[str] = []
        for raw_line in raw_lines:
            if not isinstance(raw_line, dict) or not isinstance(raw_line.get("text"), str):
                raise RuntimeError(f"設定ページの行形式が不正です: {title}")
            lines.append(raw_line["text"])
        return lines

    async def import_pages(self, pages: list[JsonObject]) -> str:
        url = (
            f"https://scrapbox.io/api/page-data/import/"
            f"{self.encoded_project}.json"
        )
        async with self._session_context() as session:
            async with session.post(
                url,
                headers=self._import_headers(),
                data=self._import_form(build_import_data(pages)),
            ) as response:
                response_text = await response.text()
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(
                        "Scrapboxページのインポートに失敗しました: "
                        f"status={response.status}, body={response_text[:500]}"
                    )
                return response_text

    async def delete_page(self, title: str) -> None:
        encoded_title = quote(title, safe="")
        url = f"https://scrapbox.io/api/pages/{self.encoded_project}/{encoded_title}"
        async with self._session_context() as session:
            async with session.delete(url, headers=self._read_headers()) as response:
                response_text = await response.text()
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(
                        "Scrapboxページの削除に失敗しました: "
                        f"status={response.status}, body={response_text[:500]}"
                    )

    async def _get_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
    ) -> JsonObject:
        async with session.get(url, headers=self._read_headers()) as response:
            response_text = await response.text()
            if response.status < 200 or response.status >= 300:
                raise RuntimeError(
                    "Scrapboxページデータの取得に失敗しました: "
                    f"status={response.status}, body={response_text[:500]}"
                )
            try:
                data = json.loads(response_text)
            except json.JSONDecodeError as exc:
                raise RuntimeError("Scrapbox APIが不正なJSONを返しました") from exc
        if not isinstance(data, dict):
            raise RuntimeError("Scrapbox APIのレスポンス形式が不正です")
        return data


def transform_exported_pages(
    pages: list[JsonObject],
    *,
    excluded_tags: set[str],
    excluded_icons: set[str],
    replacements: dict[str, str],
) -> list[JsonObject]:
    eligible_pages = [
        page
        for page in pages
        if not _is_excluded_page(page, excluded_tags, excluded_icons)
    ]
    title_map = {
        _page_title(page): _replace_strings(_page_title(page), replacements)
        for page in eligible_pages
    }

    return [
        _transform_page(page, title_map, replacements) for page in eligible_pages
    ]


def parse_exclusion_settings(lines: list[str]) -> tuple[set[str], set[str]]:
    tags: set[str] = set()
    icons: set[str] = set()
    for line in lines:
        tags.update(HASHTAG_PATTERN.findall(line))
        for match in INTERNAL_LINK_PATTERN.finditer(line):
            if match.group(1).strip().endswith(".icon"):
                icons.add(match.group(0))
    return tags, icons


def parse_replacement_settings(lines: list[str]) -> dict[str, str]:
    replacements: dict[str, str] = {}
    for line in lines:
        if "=>" not in line:
            continue
        source, replacement = line.split("=>", maxsplit=1)
        source = source.strip()
        replacement = replacement.strip()
        if not source or not replacement:
            raise ValueError(f"置換設定の形式が不正です: {line}")
        replacements[source] = replacement
    return replacements


def _page_title(page: JsonObject) -> str:
    title = page.get("title")
    if not isinstance(title, str) or not title:
        raise ValueError("ページタイトルが不正です")
    return title


def _transform_page(
    page: JsonObject,
    title_map: dict[str, str],
    replacements: dict[str, str],
) -> JsonObject:
    result = copy.deepcopy(page)
    result["title"] = title_map[_page_title(page)]
    raw_lines = result.get("lines")
    if not isinstance(raw_lines, list):
        raise ValueError(f"ページのlinesが不正です: {_page_title(page)}")

    transformed_lines: list[JsonValue] = []
    for raw_line in raw_lines:
        if not isinstance(raw_line, dict):
            raise ValueError(f"ページの行形式が不正です: {_page_title(page)}")
        line = copy.deepcopy(raw_line)
        text = line.get("text")
        if not isinstance(text, str):
            raise ValueError(f"ページの行テキストが不正です: {_page_title(page)}")
        line["text"] = _transform_line(text, title_map, replacements)
        transformed_lines.append(line)
    result["lines"] = transformed_lines
    return result


def _is_excluded_page(
    page: JsonObject,
    excluded_tags: set[str],
    excluded_icons: set[str],
) -> bool:
    raw_lines = page.get("lines")
    if not isinstance(raw_lines, list):
        raise ValueError(f"ページのlinesが不正です: {_page_title(page)}")
    texts: list[str] = []
    for raw_line in raw_lines:
        if not isinstance(raw_line, dict) or not isinstance(raw_line.get("text"), str):
            raise ValueError(f"ページの行形式が不正です: {_page_title(page)}")
        texts.append(raw_line["text"])
    joined = "\n".join(texts)
    return any(tag in joined.split() for tag in excluded_tags) or any(
        icon in joined for icon in excluded_icons
    )


def _transform_line(
    text: str,
    title_map: dict[str, str],
    replacements: dict[str, str],
) -> str:
    def replace_link(match: re.Match[str]) -> str:
        target = match.group(1).strip()
        if target.startswith(("http://", "https://")):
            reference = match.group(0)
        elif target in title_map:
            reference = f"[{title_map[target]}]"
        elif ATTACHMENT_REFERENCE_PATTERN.fullmatch(target):
            reference = match.group(0)
        else:
            return ""
        return reference

    transformed_parts: list[str] = []
    previous_end = 0
    for match in INTERNAL_LINK_PATTERN.finditer(text):
        transformed_parts.append(
            _replace_strings(text[previous_end : match.start()], replacements)
        )
        transformed_parts.append(replace_link(match))
        previous_end = match.end()
    transformed_parts.append(_replace_strings(text[previous_end:], replacements))
    return "".join(transformed_parts)


def _replace_strings(text: str, replacements: dict[str, str]) -> str:
    for source, replacement in replacements.items():
        text = text.replace(source, replacement)
    return text


class _ExistingSessionContext:
    def __init__(self, session: aiohttp.ClientSession):
        self.session = session

    async def __aenter__(self) -> aiohttp.ClientSession:
        return self.session

    async def __aexit__(self, *args: object) -> None:
        return None


class MirrorRunResult:
    def __init__(
        self,
        imported_pages: int,
        excluded_pages: int,
        failed_pages: int,
        created_pages: int,
        updated_pages: int,
        deleted_pages: int,
        deleted_titles: list[str],
        created_titles: list[str],
        updated_titles: list[str],
        excluded_titles: list[str],
        failed_titles: list[str],
    ):
        self.imported_pages = imported_pages
        self.excluded_pages = excluded_pages
        self.failed_pages = failed_pages
        self.created_pages = created_pages
        self.updated_pages = updated_pages
        self.deleted_pages = deleted_pages
        self.deleted_titles = deleted_titles
        self.created_titles = created_titles
        self.updated_titles = updated_titles
        self.excluded_titles = excluded_titles
        self.failed_titles = failed_titles


class MirrorService:
    def __init__(
        self,
        source: MirrorCosenseClient,
        destination: MirrorCosenseClient,
        exclusion_config_page: str,
        replacement_config_page: str,
    ):
        self.source = source
        self.destination = destination
        self.exclusion_config_page = exclusion_config_page
        self.replacement_config_page = replacement_config_page
        self._run_lock = asyncio.Lock()

    async def run(self) -> MirrorRunResult:
        async with self._run_lock:
            return await self._run_once()

    async def _run_once(self) -> MirrorRunResult:
        excluded_tags = set(DEFAULT_EXCLUDED_TAGS)
        excluded_icons = set(DEFAULT_EXCLUDED_ICONS)
        if self.exclusion_config_page:
            lines = await self.source.fetch_page_lines(self.exclusion_config_page)
            tags, icons = parse_exclusion_settings(lines)
            excluded_tags.update(tags)
            excluded_icons.update(icons)

        replacements: dict[str, str] = {}
        if self.replacement_config_page:
            lines = await self.source.fetch_page_lines(self.replacement_config_page)
            replacements = parse_replacement_settings(lines)

        source_pages = await self.source.export_pages()
        eligible_pages: list[JsonObject] = []
        failed_source_titles: set[str] = set()
        excluded_titles: list[str] = []
        failed_titles: list[str] = []
        excluded_pages = 0
        failed_pages = 0
        for page in source_pages:
            try:
                _page_title(page)
                if _is_excluded_page(page, excluded_tags, excluded_icons):
                    excluded_pages += 1
                    excluded_titles.append(_page_title(page))
                else:
                    eligible_pages.append(page)
            except Exception as error:
                failed_pages += 1
                title = page.get("title")
                if isinstance(title, str):
                    failed_source_titles.add(_replace_strings(title, replacements))
                    failed_titles.append(title)
                print(f"ミラーリング対象ページを判定できませんでした: {error}", flush=True)

        title_map = {
            _page_title(page): _replace_strings(_page_title(page), replacements)
            for page in eligible_pages
        }
        transformed_pages: list[JsonObject] = []
        for page in eligible_pages:
            try:
                transformed_pages.append(_transform_page(page, title_map, replacements))
            except Exception as error:
                failed_pages += 1
                title = page.get("title")
                if isinstance(title, str):
                    failed_source_titles.add(_replace_strings(title, replacements))
                    failed_titles.append(title)
                print(f"ミラーリング対象ページを変換できませんでした: {error}", flush=True)

        transformed_titles = [page["title"] for page in transformed_pages]
        current_titles = set(transformed_titles)
        if len(current_titles) != len(transformed_titles):
            raise RuntimeError("Publicページのタイトルが重複するためミラーリングできません")
        destination_pages = await self.destination.export_pages()
        existing_titles = {_page_title(page) for page in destination_pages}
        stale_titles: list[str] = []
        for page in destination_pages:
            title = _page_title(page)
            if title not in current_titles and title not in failed_source_titles:
                stale_titles.append(title)
        await self.destination.import_pages(transformed_pages)
        deleted_titles: list[str] = []
        for title in stale_titles:
            try:
                await self.destination.delete_page(title)
            except Exception as error:
                failed_pages += 1
                failed_titles.append(title)
                print(f"Publicページを削除できませんでした: {title}: {error}", flush=True)
            else:
                deleted_titles.append(title)
        saved_pages = await self.destination.export_pages()
        _verify_saved_pages(transformed_pages, saved_pages, deleted_titles)
        return MirrorRunResult(
            imported_pages=len(transformed_pages),
            excluded_pages=excluded_pages,
            failed_pages=failed_pages,
            created_pages=len(current_titles - existing_titles),
            updated_pages=len(current_titles & existing_titles),
            deleted_pages=len(deleted_titles),
            deleted_titles=deleted_titles,
            created_titles=[
                title for title in transformed_titles if title not in existing_titles
            ],
            updated_titles=[
                title for title in transformed_titles if title in existing_titles
            ],
            excluded_titles=excluded_titles,
            failed_titles=failed_titles,
        )


def _verify_saved_pages(
    expected_pages: list[JsonObject],
    saved_pages: list[JsonObject],
    deleted_titles: list[str],
) -> None:
    saved_by_title = {_page_title(page): page for page in saved_pages}
    for expected in expected_pages:
        title = _page_title(expected)
        saved = saved_by_title.get(title)
        if saved is None:
            raise RuntimeError(f"保存後の確認に失敗しました: {title}が見つかりません")
        for key, value in expected.items():
            if saved.get(key) != value:
                raise RuntimeError(
                    f"保存後の確認に失敗しました: {title}の{key}が一致しません"
                )
    for title in deleted_titles:
        if title in saved_by_title:
            raise RuntimeError(f"保存後の確認に失敗しました: {title}が削除されていません")
