import unittest
from unittest.mock import Mock, patch

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

    def test_start_web_server_returns_daemon_thread(self):
        import web_server

        with patch.object(web_server, "Thread") as thread_class:
            thread = thread_class.return_value
            result = web_server.start_web_server()

        thread_class.assert_called_once_with(target=web_server.run, daemon=True)
        thread.start.assert_called_once_with()
        self.assertIs(result, thread)

    def test_stop_web_server_shuts_down_running_server(self):
        import web_server

        server = Mock()
        thread = Mock()
        with patch.object(web_server, "_server", server), patch.object(
            web_server, "_server_thread", thread
        ):
            web_server.stop_web_server()

        server.shutdown.assert_called_once_with()
        thread.join.assert_called_once_with(timeout=5)


if __name__ == "__main__":
    unittest.main()
