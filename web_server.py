from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "I'm alive"

def run():
    app.run(host='0.0.0.0', port=8080)

def start_web_server():
    t = Thread(target=run)
    t.start()


def register_tactical_challenge_api():
    from tactical_challenge.http_api import create_tactical_challenge_blueprint

    app.register_blueprint(create_tactical_challenge_blueprint())
