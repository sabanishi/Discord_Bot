from pathlib import Path

from flask import Flask, send_file
from threading import Thread

BRIDGE_USER_SCRIPT = Path(__file__).parent / "tactical_challenge" / "request_bridge.user.js"
NICONICO_USER_SCRIPT = Path(__file__).parent / "niconico.user.js"

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
    from tactical_challenge.http_api import create_tactical_challenge_blueprint

    app.register_blueprint(create_tactical_challenge_blueprint())


def create_app(register_api: bool = True) -> Flask:
    app = Flask(__name__)
    _register_static_routes(app)
    if register_api:
        _register_tactical_challenge_api(app)
    return app


app = create_app(register_api=False)


def run():
    app.run(host='0.0.0.0', port=8080)


def start_web_server():
    t = Thread(target=run)
    t.start()


def register_tactical_challenge_api(app: Flask = app):
    _register_tactical_challenge_api(app)
