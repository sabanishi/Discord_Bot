import os
import sys
import unittest
from unittest.mock import patch

from tools.check_link_warnings import parse_args


class CheckLinkWarningsTests(unittest.TestCase):
    def test_parse_args_uses_environment_defaults(self):
        with patch.dict(
            os.environ,
            {
                "COSENSE_PROJECT": "project",
                "COSENSE_SID": "sid",
                "LINK_WARNING_THRESHOLD": "30",
                "LINK_WARNING_RESOLVE_THRESHOLD": "25",
                "LINK_WARNING_CONFIG_PAGE": "除外設定",
            },
            clear=True,
        ), patch.object(sys, "argv", ["check_link_warnings.py"]):
            args = parse_args()

        self.assertEqual(args.project, "project")
        self.assertEqual(args.sid, "sid")
        self.assertEqual(args.threshold, 30)
        self.assertEqual(args.resolve_threshold, 25)
        self.assertEqual(args.config_page, "除外設定")
        self.assertFalse(args.watch)

    def test_parse_args_accepts_cli_overrides(self):
        with patch.dict(os.environ, {"COSENSE_PROJECT": "environment"}, clear=True), patch.object(
            sys,
            "argv",
            [
                "check_link_warnings.py",
                "--project",
                "cli-project",
                "--sid",
                "cli-sid",
                "--threshold",
                "40",
                "--resolve-threshold",
                "20",
                "--watch",
                "--interval-seconds",
                "15",
            ],
        ):
            args = parse_args()

        self.assertEqual(args.project, "cli-project")
        self.assertEqual(args.sid, "cli-sid")
        self.assertEqual(args.threshold, 40)
        self.assertEqual(args.resolve_threshold, 20)
        self.assertTrue(args.watch)
        self.assertEqual(args.interval_seconds, 15)


if __name__ == "__main__":
    unittest.main()
