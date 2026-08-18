import unittest

from link_warning import LinkWarningState, PageSummary, extract_setting_links


class LinkWarningStateTest(unittest.TestCase):
    def setUp(self):
        self.state = LinkWarningState(warning_threshold=30, resolve_threshold=25)

    def test_initial_scan_does_not_notify(self):
        pages = [PageSummary("1", "KJ法", 40)]

        self.assertEqual(self.state.find_new_warnings(pages, set()), [])
        self.assertIn("1", self.state.warned_page_ids)

    def test_warns_once_until_resolved(self):
        self.state.find_new_warnings([PageSummary("1", "KJ法", 29)], set())

        warnings = self.state.find_new_warnings([PageSummary("1", "KJ法", 30)], set())
        self.assertEqual([page.title for page in warnings], ["KJ法"])

        self.state.mark_warned("1")
        self.assertEqual(
            self.state.find_new_warnings([PageSummary("1", "KJ法", 50)], set()),
            [],
        )
        self.assertEqual(
            self.state.find_new_warnings([PageSummary("1", "KJ法", 26)], set()),
            [],
        )

        self.state.find_new_warnings([PageSummary("1", "KJ法", 25)], set())
        warnings = self.state.find_new_warnings([PageSummary("1", "KJ法", 31)], set())
        self.assertEqual([page.title for page in warnings], ["KJ法"])

    def test_excluded_page_is_ignored(self):
        self.state.find_new_warnings([], {"diary"})
        warnings = self.state.find_new_warnings(
            [PageSummary("1", "diary", 100)],
            {"diary"},
        )
        self.assertEqual(warnings, [])


class ExtractSettingLinksTest(unittest.TestCase):
    def test_extracts_bracket_links_and_hashtags(self):
        self.assertEqual(
            extract_setting_links("#diary [人物] [読んだ本]"),
            {"diary", "人物", "読んだ本"},
        )


if __name__ == "__main__":
    unittest.main()
