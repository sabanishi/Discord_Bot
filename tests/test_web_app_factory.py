import unittest

from web_server import create_app


class WebAppFactoryTests(unittest.TestCase):
    def test_factory_registers_health_and_userscript_routes(self):
        app = create_app()
        client = app.test_client()

        self.assertEqual(client.get("/").status_code, 200)
        self.assertEqual(
            client.get("/userscripts/niconico.user.js").status_code,
            200,
        )

    def test_factory_registers_tactical_challenge_api(self):
        app = create_app()

        self.assertIn("/api/tactical-challenge/refactor", {
            rule.rule for rule in app.url_map.iter_rules()
        })

    def test_factory_can_omit_api_registration(self):
        app = create_app(register_api=False)

        self.assertNotIn("/api/tactical-challenge/refactor", {
            rule.rule for rule in app.url_map.iter_rules()
        })


if __name__ == "__main__":
    unittest.main()
