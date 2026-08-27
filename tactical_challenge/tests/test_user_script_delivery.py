from pathlib import Path
import unittest

from web_server import app


BRIDGE_SCRIPT = Path(__file__).parents[1] / "request_bridge.user.js"


class UserScriptDeliveryTest(unittest.TestCase):
    def test_serves_installable_bridge_script(self):
        response = app.test_client().get(
            "/userscripts/tactical-challenge-bridge.user.js"
        )
        self.addCleanup(response.close)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_data(as_text=True),
            BRIDGE_SCRIPT.read_text(encoding="utf-8"),
        )
        self.assertEqual(response.mimetype, "application/javascript")
        self.assertNotIn("attachment", response.headers["Content-Disposition"])
        self.assertIn("// ==UserScript==", response.get_data(as_text=True))
        self.assertIn("// @grant        GM.xmlHttpRequest", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
