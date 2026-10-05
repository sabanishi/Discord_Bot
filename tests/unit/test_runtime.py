import unittest
from dataclasses import replace
from unittest.mock import patch

from app.config import AppConfig
from app.runtime import RuntimeState, initialize_runtime


class RuntimeTests(unittest.TestCase):
    def test_initialize_runtime_builds_dependencies(self):
        config = AppConfig(
            token="token",
            default_channel_id=1,
            alert_channel_id=2,
            cosense_project="project",
            cosense_sid="connect.sid=value",
            create_page_time=(7, 0),
            check_page_time=(23, 0),
            mention_target="@user",
            link_warning_enabled=False,
            link_warning_interval_minutes=60,
            link_warning_config_page="config",
            link_warning_threshold=30,
            link_warning_resolve_threshold=29,
            mirror_public_project="public",
            mirror_exclusion_config_page="除外設定",
            mirror_replacement_config_page="置換設定",
        )

        with patch("app.runtime.load_config", return_value=config), patch(
            "app.runtime.DiaryClient"
        ) as diary_client, patch.object(RuntimeState, "validate_env") as validate:
            state = initialize_runtime()

        self.assertIsInstance(state, RuntimeState)
        self.assertIs(state.config, config)
        self.assertIs(state.diary_client, diary_client.return_value)
        self.assertEqual(state.link_warning_state.warning_threshold, 30)
        diary_client.assert_called_once_with("project", "connect.sid=value")
        validate.assert_called_once_with()

    def test_validate_env_rejects_missing_required_values(self):
        state = RuntimeState(config=AppConfig(
            token="",
            default_channel_id=1,
            alert_channel_id=2,
            cosense_project="project",
            cosense_sid="sid",
            create_page_time=(7, 0),
            check_page_time=(23, 0),
            mention_target="@user",
            link_warning_enabled=False,
            link_warning_interval_minutes=60,
            link_warning_config_page="config",
            link_warning_threshold=30,
            link_warning_resolve_threshold=29,
        ))

        with self.assertRaisesRegex(RuntimeError, "DISCORD_TOKEN"):
            state.validate_env()

    def test_validate_env_rejects_missing_mirroring_configuration(self):
        state = RuntimeState(config=AppConfig(
            token="token",
            default_channel_id=1,
            alert_channel_id=2,
            cosense_project="private",
            cosense_sid="sid",
            create_page_time=(7, 0),
            check_page_time=(23, 0),
            mention_target="@user",
            link_warning_enabled=False,
            link_warning_interval_minutes=60,
            link_warning_config_page="config",
            link_warning_threshold=30,
            link_warning_resolve_threshold=29,
        ))

        with self.assertRaisesRegex(RuntimeError, "MIRROR_PUBLIC_PROJECT"):
            state.validate_env()

    def test_validate_env_rejects_missing_each_mirroring_setting(self):
        config = AppConfig(
            token="token",
            default_channel_id=1,
            alert_channel_id=2,
            cosense_project="private",
            cosense_sid="sid",
            create_page_time=(7, 0),
            check_page_time=(23, 0),
            mention_target="@user",
            link_warning_enabled=False,
            link_warning_interval_minutes=60,
            link_warning_config_page="config",
            link_warning_threshold=30,
            link_warning_resolve_threshold=29,
            mirror_public_project="public",
            mirror_exclusion_config_page="除外設定",
            mirror_replacement_config_page="置換設定",
        )

        for field, env_name in (
            ("mirror_public_project", "MIRROR_PUBLIC_PROJECT"),
            ("mirror_exclusion_config_page", "MIRROR_EXCLUSION_CONFIG_PAGE"),
            ("mirror_replacement_config_page", "MIRROR_REPLACEMENT_CONFIG_PAGE"),
        ):
            with self.subTest(field=field):
                state = RuntimeState(
                    config=replace(config, **{field: ""})
                )
                with self.assertRaisesRegex(RuntimeError, env_name):
                    state.validate_env()

    def test_validate_env_rejects_whitespace_only_public_project(self):
        state = RuntimeState(config=AppConfig(
            token="token",
            default_channel_id=1,
            alert_channel_id=2,
            cosense_project="private",
            cosense_sid="sid",
            create_page_time=(7, 0),
            check_page_time=(23, 0),
            mention_target="@user",
            link_warning_enabled=False,
            link_warning_interval_minutes=60,
            link_warning_config_page="config",
            link_warning_threshold=30,
            link_warning_resolve_threshold=29,
            mirror_public_project="   ",
            mirror_exclusion_config_page="除外設定",
            mirror_replacement_config_page="置換設定",
        ))

        with self.assertRaisesRegex(RuntimeError, "MIRROR_PUBLIC_PROJECT"):
            state.validate_env()

    def test_validate_env_rejects_whitespace_only_cosense_sid(self):
        state = RuntimeState(config=AppConfig(
            token="token",
            default_channel_id=1,
            alert_channel_id=2,
            cosense_project="private",
            cosense_sid="   ",
            create_page_time=(7, 0),
            check_page_time=(23, 0),
            mention_target="@user",
            link_warning_enabled=False,
            link_warning_interval_minutes=60,
            link_warning_config_page="config",
            link_warning_threshold=30,
            link_warning_resolve_threshold=29,
        ))

        with self.assertRaisesRegex(RuntimeError, "COSENSE_SID"):
            state.validate_env()

    def test_initialize_runtime_disables_mirroring_service(self):
        config = AppConfig(
            token="token",
            default_channel_id=1,
            alert_channel_id=2,
            cosense_project="private",
            cosense_sid="private-sid",
            create_page_time=(7, 0),
            check_page_time=(23, 0),
            mention_target="@user",
            link_warning_enabled=False,
            link_warning_interval_minutes=60,
            link_warning_config_page="config",
            link_warning_threshold=30,
            link_warning_resolve_threshold=29,
            mirror_public_project="public",
            mirror_exclusion_config_page="除外設定",
            mirror_replacement_config_page="置換設定",
        )

        with patch("app.runtime.load_config", return_value=config), patch(
            "app.runtime.DiaryClient"
        ), patch("app.runtime.MirrorCosenseClient") as client, patch.object(
            RuntimeState, "validate_env"
        ):
            state = initialize_runtime()

        self.assertIsNone(state.mirror_service)
        self.assertEqual(client.call_count, 0)
