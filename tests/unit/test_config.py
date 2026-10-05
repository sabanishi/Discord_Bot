import unittest

from app.config import AppConfig, load_config, normalize_sid, validate_link_warning_thresholds


class ConfigTests(unittest.TestCase):
    def test_normalize_sid_accepts_cookie_prefix_and_whitespace(self):
        self.assertEqual(normalize_sid("  connect.sid= session  "), "session")
        self.assertEqual(normalize_sid(" session "), "session")

    def test_validate_link_warning_thresholds_rejects_invalid_order(self):
        self.assertEqual(validate_link_warning_thresholds(30, 25), 25)
        with self.assertRaises(ValueError):
            validate_link_warning_thresholds(30, 30)

    def test_load_config_reads_values_and_defaults(self):
        config = load_config(
            {
                "DISCORD_TOKEN": "token",
                "DISCORD_DEFAULT_CHANNEL_ID": "123",
                "DISCORD_ALERT_CHANNEL_ID": "456",
                "COSENSE_PROJECT": "project",
                "COSENSE_SID": "connect.sid=session",
                "MIRROR_PUBLIC_PROJECT": "public-project",
                "MIRROR_EXCLUSION_CONFIG_PAGE": "除外設定",
                "MIRROR_REPLACEMENT_CONFIG_PAGE": "置換設定",
                "MENTION_TARGET": "789",
                "CREATE_PAGE_TIME": "06:30",
                "LINK_WARNING_ENABLED": "off",
            }
        )

        self.assertIsInstance(config, AppConfig)
        self.assertEqual(config.default_channel_id, 123)
        self.assertEqual(config.alert_channel_id, 456)
        self.assertEqual(config.create_page_time, (6, 30))
        self.assertEqual(config.check_page_time, (21, 15))
        self.assertFalse(config.link_warning_enabled)
        self.assertEqual(config.mention_target, "<@789>")
        self.assertEqual(config.link_warning_interval_minutes, 30)

    def test_resolve_threshold_is_lowered_when_not_below_warning_threshold(self):
        config = load_config(
            {
                "LINK_WARNING_THRESHOLD": "10",
                "LINK_WARNING_RESOLVE_THRESHOLD": "10",
            }
        )

        self.assertEqual(config.link_warning_threshold, 10)
        self.assertEqual(config.link_warning_resolve_threshold, 9)

    def test_invalid_values_are_rejected(self):
        cases = [
            ({"LINK_WARNING_ENABLED": "maybe"}, "LINK_WARNING_ENABLED"),
            ({"LINK_WARNING_INTERVAL_MINUTES": "0"}, "LINK_WARNING_INTERVAL_MINUTES"),
            ({"CREATE_PAGE_TIME": "25:00"}, "CREATE_PAGE_TIME"),
            ({"LINK_WARNING_THRESHOLD": "not-an-integer"}, "LINK_WARNING_THRESHOLD"),
        ]

        for environ, env_name in cases:
            with self.subTest(env_name=env_name):
                with self.assertRaisesRegex(RuntimeError, env_name):
                    load_config(environ)

    def test_load_config_reads_mirroring_settings(self):
        config = load_config(
            {
                "MIRROR_PUBLIC_PROJECT": "public-project",
                "MIRROR_EXCLUSION_CONFIG_PAGE": "ミラー除外設定",
                "MIRROR_REPLACEMENT_CONFIG_PAGE": "ミラー置換設定",
                "MIRROR_RUN_HOURS": "8,16,24",
            }
        )

        self.assertEqual(config.mirror_public_project, "public-project")
        self.assertEqual(config.mirror_exclusion_config_page, "ミラー除外設定")
        self.assertEqual(config.mirror_replacement_config_page, "ミラー置換設定")
        self.assertEqual(config.mirror_run_hours, (8, 16, 0))

    def test_mirroring_run_hours_have_default_schedule(self):
        config = load_config({})

        self.assertEqual(config.mirror_run_hours, (8, 16, 0))

    def test_invalid_mirroring_run_hours_are_rejected(self):
        cases = ["8,16", "8,8,24", "8,25,24", "8,16,24:00"]

        for value in cases:
            with self.subTest(value=value):
                with self.assertRaisesRegex(RuntimeError, "MIRROR_RUN_HOURS"):
                    load_config({"MIRROR_RUN_HOURS": value})


if __name__ == "__main__":
    unittest.main()
