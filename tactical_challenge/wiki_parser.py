from html.parser import HTMLParser
from urllib.parse import urljoin

from .wiki_types import StudentIcon


class WikiIconParseError(ValueError):
    pass


def normalize_student_name(name: str) -> str:
    """Wikiの正式名称をScrapboxで使う表記へ正規化する。"""
    return name.strip().translate(str.maketrans({"（": "(", "）": ")"}))


class _CharacterIconParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.anchor_titles: list[str | None] = []
        self.icons: list[StudentIcon] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)

        if tag == "a":
            self.anchor_titles.append(attributes.get("title"))
            return

        if tag != "img" or not self.anchor_titles:
            return

        title = self.anchor_titles[-1]
        image_path = attributes.get("data-src") or attributes.get("src")
        alt = attributes.get("alt", "")

        if not title or not image_path:
            return
        if "icon" not in alt.lower():
            return
        if not image_path.startswith(("attach/", "attach2/")):
            return

        self.icons.append(
            StudentIcon(
                name=normalize_student_name(title),
                image_url=urljoin(self.base_url, image_path),
            )
        )

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.anchor_titles:
            self.anchor_titles.pop()


def parse_student_icons(html: str, base_url: str) -> list[StudentIcon]:
    """キャラアイコン表のHTMLから正式名称と画像URLを抽出する。"""
    parser = _CharacterIconParser(base_url)
    parser.feed(html)
    parser.close()

    unique_icons: dict[str, StudentIcon] = {}
    for icon in parser.icons:
        # 同じ衣装の別表情が後続行に載る場合があるため、先頭の通常画像を採用する。
        unique_icons.setdefault(icon.name, icon)

    if not unique_icons:
        raise WikiIconParseError("キャラアイコンを1件も取得できませんでした")

    return list(unique_icons.values())
