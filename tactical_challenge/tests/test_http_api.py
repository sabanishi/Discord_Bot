import os
import unittest
from unittest.mock import patch

from web_server import app
from tactical_challenge import TargetPageResult
from tactical_challenge.http_api import create_tactical_challenge_blueprint


class TacticalChallengeHttpApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.register_blueprint(create_tactical_challenge_blueprint())

    def test_refactors_requested_page_and_returns_summary(self):
        with patch.dict(
            os.environ,
            {"COSENSE_PROJECT": "p", "COSENSE_SID": "s", "GYAZO_ACCESS_TOKEN": "g"},
        ), patch(
            "tactical_challenge.http_api.refactor_target_pages",
            return_value=[TargetPageResult("対象", 2, ("エイミ",))],
        ) as refactor:
            response = app.test_client().post(
                "/api/tactical-challenge/refactor",
                json={"title": "対象"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["changed_lines"], 2)
        self.assertEqual(response.get_json()["created_icons"], 1)
        self.assertEqual(refactor.call_args.kwargs["target_title"], "対象")

    def test_rejects_non_target_page(self):
        with patch.dict(
            os.environ,
            {"COSENSE_PROJECT": "p", "COSENSE_SID": "s", "GYAZO_ACCESS_TOKEN": "g"},
        ), patch(
            "tactical_challenge.http_api.refactor_target_pages",
            side_effect=ValueError("対象外"),
        ):
            response = app.test_client().post(
                "/api/tactical-challenge/refactor",
                json={"title": "対象外"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "対象外"})


if __name__ == "__main__":
    unittest.main()
