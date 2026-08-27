from pathlib import Path

from flask import Flask, send_file
from threading import Thread

app = Flask('')
BRIDGE_USER_SCRIPT = Path(__file__).parent / "tactical_challenge" / "request_bridge.user.js"

@app.route('/')
def home():
    return "I'm alive"


@app.route('/userscripts/tactical-challenge-bridge.user.js')
def tactical_challenge_bridge_user_script():
    """UserscriptsとTampermonkeyへ通信中継スクリプトを配信する。"""
    return send_file(
        BRIDGE_USER_SCRIPT,
        mimetype="application/javascript",
        as_attachment=True,
        download_name="tactical-challenge-bridge.user.js",
    )

def run():
    app.run(host='0.0.0.0', port=8080)

def start_web_server():
    t = Thread(target=run)
    t.start()


def register_tactical_challenge_api():
    from tactical_challenge.http_api import create_tactical_challenge_blueprint

    app.register_blueprint(create_tactical_challenge_blueprint())
