import os
import unittest
from unittest.mock import patch

from web_server import create_app
from tactical_challenge import TargetPageResult
from tactical_challenge.http_api import create_tactical_challenge_blueprint


app = create_app(register_api=True)


class TacticalChallengeHttpApiTest(unittest.TestCase):

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

    def test_rejects_missing_or_invalid_title(self):
        client = app.test_client()

        for payload in ({}, {"title": "   "}, {"title": 123}):
            with self.subTest(payload=payload):
                response = client.post(
                    "/api/tactical-challenge/refactor",
                    json=payload,
                )

                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json(), {"error": "titleが必要です"})

    def test_rejects_missing_environment_configuration(self):
        with patch.dict(os.environ, {}, clear=True):
            response = app.test_client().post(
                "/api/tactical-challenge/refactor",
                json={"title": "対象"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "必要な環境変数が未設定です"})

    def test_returns_internal_error_and_message(self):
        with patch.dict(
            os.environ,
            {"COSENSE_PROJECT": "p", "COSENSE_SID": "s", "GYAZO_ACCESS_TOKEN": "g"},
        ), patch(
            "tactical_challenge.http_api.refactor_target_pages",
            side_effect=RuntimeError("内部エラー"),
        ):
            response = app.test_client().post(
                "/api/tactical-challenge/refactor",
                json={"title": "対象"},
            )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(response.get_json(), {"error": "内部エラー"})

    def test_options_response_has_cors_headers(self):
        response = app.test_client().options("/api/tactical-challenge/refactor")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.headers["Access-Control-Allow-Origin"], "*")
        self.assertIn("POST", response.headers["Access-Control-Allow-Methods"])


if __name__ == "__main__":
    unittest.main()
