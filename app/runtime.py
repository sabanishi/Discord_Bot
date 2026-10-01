from dataclasses import dataclass

import aiohttp

from app.config import AppConfig, load_config
from app.diary import DiaryClient
from app.link_warning import LinkWarningState


@dataclass
class RuntimeState:
    config: AppConfig | None = None
    link_warning_state: LinkWarningState | None = None
    diary_client: DiaryClient | None = None
    http_session: aiohttp.ClientSession | None = None
    tasks_started: bool = False


def initialize_runtime() -> RuntimeState:
    config = load_config()
    return RuntimeState(
        config=config,
        link_warning_state=LinkWarningState(
            warning_threshold=config.link_warning_threshold,
            resolve_threshold=config.link_warning_resolve_threshold,
        ),
        diary_client=DiaryClient(config.cosense_project, config.cosense_sid),
    )


def validate_env(state: RuntimeState) -> None:
    config = state.config
    if not config.token:
        raise RuntimeError("環境変数 DISCORD_TOKEN が設定されていません")
    if not config.default_channel_id:
        raise RuntimeError("環境変数 DISCORD_DEFAULT_CHANNEL_ID が設定されていません")
    if not config.alert_channel_id:
        raise RuntimeError("環境変数 DISCORD_ALERT_CHANNEL_ID が設定されていません")
    if not config.cosense_project:
        raise RuntimeError("環境変数 COSENSE_PROJECT が設定されていません")
    if not config.cosense_sid:
        raise RuntimeError("環境変数 COSENSE_SID が設定されていません")
