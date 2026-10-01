from dataclasses import dataclass

from .aliases import build_student_aliases, parse_alias_rules
from .page_changes import build_page_changes
from .page_parser import extract_page_students, refactor_page_lines


ALIAS_CONFIG_PAGE = "戦術対抗戦_略称"


@dataclass(frozen=True)
class TargetPageResult:
    """対象ページごとの変更行数と作成アイコン。"""

    title: str
    changed_lines: int
    created_icons: tuple[str, ...]


async def refactor_target_pages(
    wiki_client,
    gyazo_client,
    cosense_client,
    target_title: str | None = None,
):
    """不足アイコンを生成し、差分がある対象ページだけ更新する。"""
    alias_page = await cosense_client.fetch_page(ALIAS_CONFIG_PAGE)
    config = parse_alias_rules(
        line["text"]
        for line in alias_page["lines"]
        if isinstance(line, dict) and isinstance(line.get("text"), str)
    )
    icons = await wiki_client.fetch_student_icons()
    icons_by_name = {icon.name: icon for icon in icons}
    aliases = build_student_aliases(icons, config)
    results: list[TargetPageResult] = []

    target_titles = await cosense_client.fetch_target_page_titles()
    if target_title is not None:
        if target_title not in target_titles:
            raise ValueError("指定されたページは戦術対抗戦の対象ではありません")
        target_titles = [target_title]

    for title in target_titles:
        page = await cosense_client.fetch_page(title)
        before = [
            line["text"]
            for line in page["lines"]
            if isinstance(line, dict) and isinstance(line.get("text"), str)
        ]
        students = extract_page_students(before, aliases)
        created_icons: list[str] = []
        available_students: set[str] = set()
        for student_name in students:
            try:
                if await cosense_client.icon_page_exists(student_name):
                    available_students.add(student_name)
                    continue
                icon = icons_by_name[student_name]
                image = await wiki_client.fetch_icon_image(icon.image_url)
                upload = await gyazo_client.upload_image(
                    image,
                    filename=f"{student_name}.png",
                )
                if await cosense_client.ensure_icon_page(
                    student_name,
                    upload.image_url,
                ):
                    created_icons.append(student_name)
                available_students.add(student_name)
            except Exception as error:
                print(
                    f"アイコンを生成できませんでした: {student_name}: {error}",
                    flush=True,
                )

        after = refactor_page_lines(
            before,
            aliases,
            replaceable_students=available_students,
        )
        changes = build_page_changes(before, after)
        if changes:
            await cosense_client.update_page_lines(
                title,
                after,
                page,
            )
        results.append(
            TargetPageResult(
                title=title,
                changed_lines=len(changes),
                created_icons=tuple(created_icons),
            )
        )

    return results
