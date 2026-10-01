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

    def validate_env(self) -> None:
        if not self.config.token:
            raise RuntimeError("環境変数 DISCORD_TOKEN が設定されていません")
        if not self.config.default_channel_id:
            raise RuntimeError("環境変数 DISCORD_DEFAULT_CHANNEL_ID が設定されていません")
        if not self.config.alert_channel_id:
            raise RuntimeError("環境変数 DISCORD_ALERT_CHANNEL_ID が設定されていません")
        if not self.config.cosense_project:
            raise RuntimeError("環境変数 COSENSE_PROJECT が設定されていません")
        if not self.config.cosense_sid:
            raise RuntimeError("環境変数 COSENSE_SID が設定されていません")


def initialize_runtime() -> RuntimeState:
    config = load_config()
    state = RuntimeState(
        config=config,
        link_warning_state=LinkWarningState(
            warning_threshold=config.link_warning_threshold,
            resolve_threshold=config.link_warning_resolve_threshold,
        ),
        diary_client=DiaryClient(config.cosense_project, config.cosense_sid),
    )
    state.validate_env()
    return state
