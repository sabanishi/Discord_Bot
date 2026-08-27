import re
from typing import Iterable

from .wiki_parser import normalize_student_name


MEMBER_SEPARATOR_PATTERN = re.compile(r"[、,，]")
MEMBER_SEPARATOR_CAPTURE_PATTERN = re.compile(r"([、,，])")
OPPONENT_ICON_PATTERN = re.compile(r"^(.*[（(])([^（）()]+)([）)])$")
SCRAPBOX_ICON_PATTERN = re.compile(r"^\[![^\[\]]+\.icon]$")


def extract_page_students(
    lines: Iterable[str],
    aliases: dict[str, str],
) -> list[str]:
    """対戦相手アイコンと編成行から生徒の正式名称を抽出する。"""
    source_lines = list(lines)
    found: list[str] = []
    seen: set[str] = set()

    for line_index, raw_line in enumerate(source_lines):
        line = raw_line.strip()
        if not line:
            continue

        opponent_match = OPPONENT_ICON_PATTERN.fullmatch(line)
        if opponent_match is not None and _is_opponent_line(
            source_lines,
            line_index,
            aliases,
        ):
            opponent_icon = normalize_student_name(opponent_match.group(2))
            canonical_name = aliases.get(opponent_icon)
            if canonical_name is not None and canonical_name not in seen:
                seen.add(canonical_name)
                found.append(canonical_name)
            continue

        members = [
            normalize_student_name(member)
            for member in MEMBER_SEPARATOR_PATTERN.split(line)
            if member.strip()
        ]
        recognized = [aliases[member] for member in members if member in aliases]

        is_single_student = len(members) == 1 and len(recognized) == 1
        is_formation = (
            len(members) >= 2
            and len(recognized) >= 2
            and len(recognized) / len(members) >= 0.5
        )
        if not is_single_student and not is_formation:
            continue

        for canonical_name in recognized:
            if canonical_name not in seen:
                seen.add(canonical_name)
                found.append(canonical_name)

    return found


def refactor_page_lines(
    lines: Iterable[str],
    aliases: dict[str, str],
    replaceable_students: set[str] | None = None,
) -> list[str]:
    """対戦相手アイコンと編成行の生徒名をScrapboxアイコンへ置換する。"""
    source_lines = list(lines)
    return [
        _refactor_line(
            line,
            aliases,
            replace_opponent=_is_opponent_line(source_lines, index, aliases),
            replaceable_students=replaceable_students,
        ).replace("、", "・")
        for index, line in enumerate(source_lines)
    ]


def _refactor_line(
    line: str,
    aliases: dict[str, str],
    replace_opponent: bool,
    replaceable_students: set[str] | None,
) -> str:
    stripped_line = line.strip()
    if not stripped_line:
        return line

    opponent_match = OPPONENT_ICON_PATTERN.fullmatch(stripped_line)
    if opponent_match is not None and replace_opponent:
        prefix, raw_name, suffix = opponent_match.groups()
        canonical_name = aliases.get(normalize_student_name(raw_name))
        if canonical_name is None or (
            replaceable_students is not None
            and canonical_name not in replaceable_students
        ):
            return line
        replacement = f"{prefix}{_build_icon(canonical_name)}{suffix}"
        return _replace_stripped_content(line, replacement)

    parts = MEMBER_SEPARATOR_CAPTURE_PATTERN.split(line)
    member_indexes = range(0, len(parts), 2)
    member_names = [normalize_student_name(parts[index]) for index in member_indexes]
    recognized = [name in aliases for name in member_names]
    recognized_or_icon = [
        is_recognized or bool(SCRAPBOX_ICON_PATTERN.fullmatch(name))
        for name, is_recognized in zip(member_names, recognized)
    ]

    is_single_student = len(member_names) == 1 and recognized[0]
    is_formation = (
        len(member_names) >= 2
        and sum(recognized_or_icon) >= 2
        and sum(recognized_or_icon) / len(member_names) >= 0.5
    )
    if not is_single_student and not is_formation:
        return line

    for index, name, is_recognized in zip(member_indexes, member_names, recognized):
        if is_recognized and (
            replaceable_students is None
            or aliases[name] in replaceable_students
        ):
            parts[index] = _replace_stripped_content(
                parts[index],
                _build_icon(aliases[name]),
            )

    return "".join(parts)


def _is_opponent_line(
    lines: list[str],
    line_index: int,
    aliases: dict[str, str],
) -> bool:
    line = lines[line_index].strip()
    match = OPPONENT_ICON_PATTERN.fullmatch(line)
    if match is None:
        return False
    if normalize_student_name(match.group(2)) not in aliases:
        return False

    for next_line in lines[line_index + 1 :]:
        if not next_line.strip():
            continue
        return _is_multi_member_formation(next_line, aliases)
    return False


def _is_multi_member_formation(line: str, aliases: dict[str, str]) -> bool:
    members = [
        normalize_student_name(member)
        for member in MEMBER_SEPARATOR_PATTERN.split(line.strip())
        if member.strip()
    ]
    if len(members) < 2:
        return False

    recognized_or_icon_count = sum(
        member in aliases or bool(SCRAPBOX_ICON_PATTERN.fullmatch(member))
        for member in members
    )
    return (
        recognized_or_icon_count >= 2
        and recognized_or_icon_count / len(members) >= 0.5
    )


def _build_icon(canonical_name: str) -> str:
    return f"[!{canonical_name}.icon]"


def _replace_stripped_content(original: str, replacement: str) -> str:
    leading_size = len(original) - len(original.lstrip())
    trailing_size = len(original) - len(original.rstrip())
    leading = original[:leading_size]
    trailing = original[len(original) - trailing_size :] if trailing_size else ""
    return f"{leading}{replacement}{trailing}"
