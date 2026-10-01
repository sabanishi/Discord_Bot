import unittest

from config import AppConfig, load_config


class ConfigTests(unittest.TestCase):
    def test_load_config_reads_values_and_defaults(self):
        config = load_config(
            {
                "DISCORD_TOKEN": "token",
                "DISCORD_DEFAULT_CHANNEL_ID": "123",
                "DISCORD_ALERT_CHANNEL_ID": "456",
                "COSENSE_PROJECT": "project",
                "COSENSE_SID": "connect.sid=session",
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


if __name__ == "__main__":
    unittest.main()
