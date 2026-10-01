from datetime import datetime, timedelta
import json
from pathlib import Path
from urllib.parse import quote

import aiohttp


def build_page_from_template(
    target_date: datetime,
    template_path: Path = Path("template.txt"),
) -> tuple[str, list[str]]:
    today = target_date.date()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)

    template = template_path.read_text(encoding="utf-8")
    text = (
        template
        .replace("${year}", today.strftime("%Y"))
        .replace("${month}", today.strftime("%m"))
        .replace("${today}", today.strftime("%Y-%m-%d"))
        .replace("${yesterday}", yesterday.strftime("%Y-%m-%d"))
        .replace("${tomorrow}", tomorrow.strftime("%Y-%m-%d"))
    )
    lines = text.splitlines()

    if not lines or not lines[0].strip():
        raise ValueError("template.txt の1行目にはページタイトルになる ${today} が必要です")

    return lines[0], lines


def normalize_lines(lines: list[str]) -> list[str]:
    """比較用に末尾の空行だけ無視する。"""
    normalized = list(lines)
    while normalized and normalized[-1] == "":
        normalized.pop()
    return normalized


class DiaryClient:
    def __init__(self, project: str, sid: str, session: aiohttp.ClientSession | None = None):
        self.project = project
        self.sid = sid.removeprefix("connect.sid=").strip()
        self.session = session

    def _session_context(self):
        if self.session is not None:
            return _ExistingSessionContext(self.session)
        return aiohttp.ClientSession()

    @property
    def encoded_project(self) -> str:
        return quote(self.project, safe="")

    def page_url(self, title: str) -> str:
        return (
            f"https://scrapbox.io/{self.encoded_project}/"
            f"{quote(title, safe='')}"
        )

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
    def _import_form(import_data: dict) -> aiohttp.FormData:
        form = aiohttp.FormData()
        form.add_field(
            "import-file",
            json.dumps(import_data, ensure_ascii=False).encode("utf-8"),
            filename="import.json",
            content_type="application/octet-stream",
        )
        return form

    async def create_page(self, title: str, lines: list[str]) -> str:
        """日記ページを作成し、保存後のページURLを返す"""
        url = f"https://scrapbox.io/api/page-data/import/{self.encoded_project}.json"
        import_data = {"pages": [{"title": title, "lines": lines}]}

        async with self._session_context() as session:
            async with session.post(
                url,
                headers=self._import_headers(),
                data=self._import_form(import_data),
            ) as response:
                response_text = await response.text()
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(
                        f"Scrapboxページ作成に失敗しました:\n"
                        f"status={response.status}, body={response_text}"
                    )
        return self.page_url(title)

    async def fetch_page_lines(self, title: str) -> list[str]:
        """指定した日記ページを取得し、本文行だけを返す"""
        encoded_title = quote(title, safe="")
        url = f"https://scrapbox.io/api/pages/{self.encoded_project}/{encoded_title}"

        async with self._session_context() as session:
            async with session.get(url, headers=self._read_headers()) as response:
                response_text = await response.text()
                if response.status == 404:
                    raise RuntimeError(f"Scrapboxページが見つかりません:\n{title}")
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(
                        f"Scrapboxページ取得に失敗しました:\n"
                        f"status={response.status}, body={response_text}"
                    )
                data = json.loads(response_text)

        if "lines" not in data or not isinstance(data["lines"], list):
            raise RuntimeError(
                f"Scrapboxページ取得結果が不正です:\n"
                f"title:\n{title}\nresponse_text:\n{response_text}"
            )
        lines = []
        for line in data["lines"]:
            if not isinstance(line, dict) or not isinstance(line.get("text", ""), str):
                raise RuntimeError("Scrapboxページ取得結果の行形式が不正です")
            lines.append(line.get("text", ""))
        return lines


class _ExistingSessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *args):
        return None
