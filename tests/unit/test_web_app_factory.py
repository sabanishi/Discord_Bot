import unittest
from unittest.mock import Mock, patch

from app.web_server import WebServer, create_app


class WebAppFactoryTests(unittest.TestCase):
    def test_factory_registers_health_and_userscript_routes(self):
        app = create_app()
        client = app.test_client()

        self.assertEqual(client.get("/").status_code, 200)
        response = client.get("/userscripts/niconico.user.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("application/javascript", response.content_type)
        self.assertIn("Cosense Niconico Thumbnail Bridge", response.get_data(as_text=True))
        response.close()

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
        import app.web_server as web_server
        server = WebServer(register_api=False)
        with patch.object(web_server, "Thread") as thread_class:
            thread = thread_class.return_value
            result = server.start()

        thread_class.assert_called_once_with(target=server.run, daemon=True)
        thread.start.assert_called_once_with()
        self.assertIs(result, thread)

    def test_stop_web_server_shuts_down_running_server(self):
        server = WebServer(register_api=False)
        running_server = Mock()
        thread = Mock()
        server._state.server = running_server
        server._state.thread = thread
        server.stop()

        running_server.shutdown.assert_called_once_with()
        thread.join.assert_called_once_with(timeout=5)


if __name__ == "__main__":
    unittest.main()
