from dataclasses import dataclass
from typing import Iterable


class PageChangeError(ValueError):
    pass


@dataclass(frozen=True)
class PageChange:
    """ページ内の1行に対する変更内容。"""

    line_number: int
    before: str
    after: str


def build_page_changes(
    before_lines: Iterable[str],
    after_lines: Iterable[str],
) -> list[PageChange]:
    """変更された行だけを1始まりの行番号とともに返す。"""
    before = list(before_lines)
    after = list(after_lines)
    if len(before) != len(after):
        raise PageChangeError("変更前後のページ行数が一致しません")

    return [
        PageChange(line_number, before_line, after_line)
        for line_number, (before_line, after_line) in enumerate(
            zip(before, after),
            start=1,
        )
        if before_line != after_line
    ]
