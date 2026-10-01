"""戦術対抗戦ページの自動リファクタ機能。"""

from .aliases import (
    AliasConfig,
    AliasCollisionError,
    AliasRuleParseError,
    build_student_aliases,
    parse_alias_rules,
)
from .wiki_client import BlueArchiveWikiClient, StudentIcon
from .wiki_parser import WikiIconParseError, parse_student_icons
from .page_parser import extract_page_students, refactor_page_lines
from .cosense_client import (
    IconPageError,
    TacticalChallengeCosenseClient,
    TargetPageParseError,
    build_icon_page_import_data,
    build_icon_page_title,
    build_page_update_import_data,
    is_ready_icon_page,
    is_persistent_cosense_page,
    parse_target_page_titles,
)
from .target_page_service import TargetPageResult, refactor_target_pages
from .unknown_students import find_unrecognized_students
from .page_changes import PageChange, PageChangeError, build_page_changes
from .gyazo_client import (
    GyazoClient,
    GyazoUpload,
    GyazoUploadError,
    parse_gyazo_upload_response,
)

__all__ = [
    "BlueArchiveWikiClient",
    "GyazoClient",
    "GyazoUpload",
    "GyazoUploadError",
    "IconPageError",
    "AliasConfig",
    "AliasCollisionError",
    "AliasRuleParseError",
    "PageChange",
    "PageChangeError",
    "StudentIcon",
    "TacticalChallengeCosenseClient",
    "TargetPageParseError",
    "TargetPageResult",
    "WikiIconParseError",
    "build_student_aliases",
    "build_icon_page_import_data",
    "build_icon_page_title",
    "build_page_update_import_data",
    "build_page_changes",
    "extract_page_students",
    "find_unrecognized_students",
    "is_persistent_cosense_page",
    "is_ready_icon_page",
    "parse_alias_rules",
    "parse_gyazo_upload_response",
    "parse_student_icons",
    "parse_target_page_titles",
    "refactor_page_lines",
    "refactor_target_pages",
]
