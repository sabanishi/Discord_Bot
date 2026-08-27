from difflib import SequenceMatcher
from typing import Iterable

from .page_parser import (
    MEMBER_SEPARATOR_PATTERN,
    OPPONENT_ICON_PATTERN,
    SCRAPBOX_ICON_PATTERN,
    _is_multi_member_formation,
)
from .wiki_parser import normalize_student_name


SUGGESTION_CUTOFF = 0.6
SUGGESTION_LIMIT = 3


def find_unrecognized_students(
    lines: Iterable[str],
    aliases: dict[str, str],
) -> dict[str, tuple[str, ...]]:
    """編成と対戦相手欄の未認識名を、正式名称の候補とともに返す。"""
    source_lines = list(lines)
    unknown_names: dict[str, tuple[str, ...]] = {}

    for line_index, raw_line in enumerate(source_lines):
        line = raw_line.strip()
        if not line:
            continue

        opponent_match = OPPONENT_ICON_PATTERN.fullmatch(line)
        if opponent_match is not None and _has_following_formation(
            source_lines,
            line_index,
            aliases,
        ):
            name = normalize_student_name(opponent_match.group(2))
            if name not in aliases:
                unknown_names.setdefault(name, _find_candidates(name, aliases))
            continue

        if not _is_multi_member_formation(line, aliases):
            continue

        members = [
            normalize_student_name(member)
            for member in MEMBER_SEPARATOR_PATTERN.split(line)
            if member.strip()
        ]
        for name in members:
            if name in aliases or SCRAPBOX_ICON_PATTERN.fullmatch(name):
                continue
            unknown_names.setdefault(name, _find_candidates(name, aliases))

    return unknown_names


def _has_following_formation(
    lines: list[str],
    line_index: int,
    aliases: dict[str, str],
) -> bool:
    for next_line in lines[line_index + 1 :]:
        if not next_line.strip():
            continue
        return _is_multi_member_formation(next_line, aliases)
    return False


def _find_candidates(
    unknown_name: str,
    aliases: dict[str, str],
) -> tuple[str, ...]:
    scored_aliases = sorted(
        (
            (SequenceMatcher(None, unknown_name, alias).ratio(), alias)
            for alias in aliases
        ),
        key=lambda item: (-item[0], item[1]),
    )

    candidates: list[str] = []
    for score, alias in scored_aliases:
        if score < SUGGESTION_CUTOFF:
            break
        canonical_name = aliases[alias]
        if canonical_name not in candidates:
            candidates.append(canonical_name)
        if len(candidates) >= SUGGESTION_LIMIT:
            break

    return tuple(candidates)
