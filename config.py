import os
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True)
class AppConfig:
    token: str | None
    default_channel_id: int
    alert_channel_id: int
    cosense_project: str | None
    cosense_sid: str | None
    mention_target: str
    create_page_time: tuple[int, int]
    check_page_time: tuple[int, int]
    link_warning_enabled: bool
    link_warning_interval_minutes: int
    link_warning_threshold: int
    link_warning_resolve_threshold: int
    link_warning_config_page: str


def _parse_bool(value: str, env_name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"環境変数 {env_name} は true または false で指定してください")


def _parse_int(value: str, env_name: str, minimum: int = 0) -> int:
    try:
        parsed = int(value.strip())
    except ValueError as exc:
        raise RuntimeError(f"環境変数 {env_name} は整数で指定してください") from exc

    if parsed < minimum:
        raise RuntimeError(f"環境変数 {env_name} は {minimum} 以上で指定してください")
    return parsed


def _parse_time(value: str, env_name: str) -> tuple[int, int]:
    try:
        hour_text, minute_text = value.split(":")
        hour = int(hour_text)
        minute = int(minute_text)
    except ValueError:
        raise RuntimeError(f"環境変数 {env_name} は HH:MM 形式で指定してください\n現在の値: {value}")

    if not 0 <= hour <= 23:
        raise RuntimeError(f"環境変数 {env_name} の時が不正です。0〜23で指定してください\n現在の値: {value}")
    if not 0 <= minute <= 59:
        raise RuntimeError(f"環境変数 {env_name} の分が不正です。0〜59で指定してください\n現在の値: {value}")
    return hour, minute


def load_config(environ: Mapping[str, str] | None = None) -> AppConfig:
    values = os.environ if environ is None else environ
    mention_id = values.get("MENTION_TARGET", "").strip()
    mention_target = f"<@{mention_id}>" if mention_id else ""
    warning_threshold = _parse_int(
        values.get("LINK_WARNING_THRESHOLD", "30"),
        "LINK_WARNING_THRESHOLD",
        minimum=1,
    )
    resolve_threshold = _parse_int(
        values.get("LINK_WARNING_RESOLVE_THRESHOLD", "25"),
        "LINK_WARNING_RESOLVE_THRESHOLD",
    )
    if resolve_threshold >= warning_threshold:
        resolve_threshold = max(0, warning_threshold - 1)
        print(
            "LINK_WARNING_RESOLVE_THRESHOLD が LINK_WARNING_THRESHOLD 未満ではないため、"
            f"{resolve_threshold} に補正します",
            flush=True,
        )

    return AppConfig(
        token=values.get("DISCORD_TOKEN"),
        default_channel_id=_parse_int(
            values.get("DISCORD_DEFAULT_CHANNEL_ID", "0"),
            "DISCORD_DEFAULT_CHANNEL_ID",
        ),
        alert_channel_id=_parse_int(
            values.get("DISCORD_ALERT_CHANNEL_ID", "0"),
            "DISCORD_ALERT_CHANNEL_ID",
        ),
        cosense_project=values.get("COSENSE_PROJECT"),
        cosense_sid=values.get("COSENSE_SID"),
        mention_target=mention_target,
        create_page_time=_parse_time(
            values.get("CREATE_PAGE_TIME", "7:00"), "CREATE_PAGE_TIME"
        ),
        check_page_time=_parse_time(
            values.get("CHECK_PAGE_TIME", "21:15"), "CHECK_PAGE_TIME"
        ),
        link_warning_enabled=_parse_bool(
            values.get("LINK_WARNING_ENABLED", "true"), "LINK_WARNING_ENABLED"
        ),
        link_warning_interval_minutes=_parse_int(
            values.get("LINK_WARNING_INTERVAL_MINUTES", "30"),
            "LINK_WARNING_INTERVAL_MINUTES",
            minimum=1,
        ),
        link_warning_threshold=warning_threshold,
        link_warning_resolve_threshold=resolve_threshold,
        link_warning_config_page=values.get("LINK_WARNING_CONFIG_PAGE", "").strip(),
    )
