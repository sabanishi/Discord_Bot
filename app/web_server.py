from pathlib import Path
from dataclasses import dataclass

from flask import Flask, send_file
from threading import Thread
from werkzeug.serving import make_server

PROJECT_ROOT = Path(__file__).parent.parent
USER_SCRIPTS_DIR = PROJECT_ROOT / "resources" / "userscripts"
BRIDGE_USER_SCRIPT = USER_SCRIPTS_DIR / "tactical_challenge-bridge.user.js"
NICONICO_USER_SCRIPT = USER_SCRIPTS_DIR / "niconico.user.js"

def _register_static_routes(app: Flask) -> None:
    @app.route('/')
    def home():
        return "I'm alive"

    @app.route('/userscripts/tactical-challenge-bridge.user.js')
    def tactical_challenge_bridge_user_script():
        """UserscriptsとTampermonkeyへ通信中継スクリプトを配信する。"""
        return send_file(
            BRIDGE_USER_SCRIPT,
            mimetype="application/javascript",
            as_attachment=False,
            download_name="tactical-challenge-bridge.user.js",
        )

    @app.route('/userscripts/niconico.user.js')
    def niconico_user_script():
        """ニコニコ動画のサムネイル取得UserScriptを配信する。"""
        return send_file(
            NICONICO_USER_SCRIPT,
            mimetype="application/javascript",
            as_attachment=False,
            download_name="niconico.user.js",
        )


def _register_tactical_challenge_api(app: Flask) -> None:
    if "tactical_challenge" in app.blueprints:
        return
    from app.tactical_challenge.http_api import create_tactical_challenge_blueprint

    app.register_blueprint(create_tactical_challenge_blueprint())


def create_app(register_api: bool = True) -> Flask:
    app = Flask(__name__)
    _register_static_routes(app)
    if register_api:
        _register_tactical_challenge_api(app)
    return app


class WebServer:
    @dataclass
    class State:
        server: object | None = None
        thread: Thread | None = None

    def __init__(self, register_api: bool = True):
        self.app = create_app(register_api=register_api)
        self._state = self.State()

    def run(self) -> None:
        self._state.server = make_server("0.0.0.0", 8080, self.app)
        self._state.server.serve_forever()

    def start(self):
        self._state.thread = Thread(target=self.run, daemon=True)
        self._state.thread.start()
        return self._state.thread

    def stop(self) -> None:
        if self._state.server is not None:
            self._state.server.shutdown()
        if self._state.thread is not None:
            self._state.thread.join(timeout=5)
        self._state = self.State()
