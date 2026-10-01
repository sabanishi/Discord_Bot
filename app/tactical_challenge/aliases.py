from dataclasses import dataclass
import re
from typing import Iterable

from .wiki_parser import normalize_student_name
from .wiki_types import StudentIcon


CONFIG_PAGE_TITLE = "戦術対抗戦_略称"
VARIANT_NAME_PATTERN = re.compile(r"^(.+?)\((.+)\)$")
DIRECT_ALIAS_PATTERN = re.compile(r"^(.+?)\s*->\s*(.+)$")


class AliasRuleParseError(ValueError):
    pass


class AliasCollisionError(ValueError):
    pass


@dataclass(frozen=True)
class AliasConfig:
    """衣装の短縮規則と生徒固有の別名設定。"""

    variant_aliases: dict[str, tuple[str, ...]]
    direct_aliases: dict[str, str]


def parse_alias_rules(lines: Iterable[str]) -> AliasConfig:
    """Scrapboxの略称設定ページから衣装名ごとの短縮形を読み取る。"""
    source_lines = list(lines)
    has_page_title = any(
        normalize_student_name(line.strip()) == CONFIG_PAGE_TITLE
        for line in source_lines
        if line.strip()
    )
    common_indent = _find_common_config_indent(source_lines) if has_page_title else 0
    rules: dict[str, list[str]] = {}
    direct_aliases: dict[str, str] = {}
    current_variant: str | None = None

    for line_number, original_line in enumerate(source_lines, start=1):
        original_value = normalize_student_name(original_line.strip())
        if (
            not original_value
            or original_value == CONFIG_PAGE_TITLE
            or original_value.startswith("#")
        ):
            continue
        raw_line = original_line[common_indent:]
        value = normalize_student_name(raw_line.strip())

        is_child = raw_line[0].isspace()
        if not is_child:
            direct_match = DIRECT_ALIAS_PATTERN.fullmatch(value)
            if direct_match is not None:
                alias, canonical_name = direct_match.groups()
                alias = normalize_student_name(alias)
                canonical_name = normalize_student_name(canonical_name)
                existing = direct_aliases.get(alias)
                if existing is not None and existing != canonical_name:
                    raise AliasRuleParseError(
                        f"個別別名が重複しています: {alias}（{line_number}行目）"
                    )
                direct_aliases[alias] = canonical_name
                current_variant = None
                continue

            if value in rules:
                raise AliasRuleParseError(
                    f"衣装名が重複しています: {value}（{line_number}行目）"
                )
            current_variant = value
            rules[current_variant] = []
            continue

        if current_variant is None:
            raise AliasRuleParseError(
                f"衣装名より前に略称があります（{line_number}行目）"
            )
        if value == current_variant or value in rules[current_variant]:
            continue
        rules[current_variant].append(value)

    if not rules and not direct_aliases:
        raise AliasRuleParseError("略称設定を1件も取得できませんでした")

    return AliasConfig(
        variant_aliases={
            variant: tuple(aliases) for variant, aliases in rules.items()
        },
        direct_aliases=direct_aliases,
    )


def _find_common_config_indent(lines: list[str]) -> int:
    """タイトルとタグを除く設定行に共通するインデント幅を返す。"""
    indents: list[int] = []
    for line in lines:
        value = normalize_student_name(line.strip())
        if not value or value == CONFIG_PAGE_TITLE or value.startswith("#"):
            continue
        indents.append(len(line) - len(line.lstrip()))
    return min(indents, default=0)


def build_student_aliases(
    students: Iterable[StudentIcon],
    config: AliasConfig,
) -> dict[str, str]:
    """正式名称と衣装略称から、入力名を正式名称へ引く索引を生成する。"""
    aliases: dict[str, str] = {}

    for student in students:
        canonical_name = normalize_student_name(student.name)
        candidates = _build_alias_candidates(
            canonical_name,
            config.variant_aliases,
        )

        for candidate in candidates:
            existing = aliases.get(candidate)
            if existing is not None and existing != canonical_name:
                raise AliasCollisionError(
                    f"略称「{candidate}」が「{existing}」と"
                    f"「{canonical_name}」で重複しています"
                )
            aliases[candidate] = canonical_name

    canonical_names = set(aliases.values())
    for alias, canonical_name in config.direct_aliases.items():
        if canonical_name not in canonical_names:
            raise AliasRuleParseError(
                f"個別別名「{alias}」の正式名称がWikiにありません: {canonical_name}"
            )
        existing = aliases.get(alias)
        if existing is not None and existing != canonical_name:
            raise AliasCollisionError(
                f"略称「{alias}」が「{existing}」と"
                f"「{canonical_name}」で重複しています"
            )
        aliases[alias] = canonical_name

    return aliases


def _build_alias_candidates(
    canonical_name: str,
    rules: dict[str, tuple[str, ...]],
) -> set[str]:
    candidates = {canonical_name}
    match = VARIANT_NAME_PATTERN.fullmatch(canonical_name)
    if match is None:
        return candidates

    base_name, variant = match.groups()
    candidates.add(f"{variant}{base_name}")

    for short_variant in rules.get(variant, ()):
        candidates.add(f"{short_variant}{base_name}")

    return candidates
