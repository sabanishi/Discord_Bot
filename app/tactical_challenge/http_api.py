import asyncio
import os

from flask import Blueprint, jsonify, request

from .cosense_client import TacticalChallengeCosenseClient
from .gyazo_client import GyazoClient
from .target_page_service import refactor_target_pages
from .wiki_client import BlueArchiveWikiClient


def create_tactical_challenge_blueprint() -> Blueprint:
    """UserScriptからの手動リファクタAPIを作成する。"""
    blueprint = Blueprint("tactical_challenge", __name__)

    @blueprint.route("/api/tactical-challenge/refactor", methods=["POST", "OPTIONS"])
    def refactor():
        if request.method == "OPTIONS":
            response = jsonify({"ok": True})
            response.status_code = 204
            return _cors(response)

        payload = request.get_json(silent=True) or {}
        title = payload.get("title")
        if not isinstance(title, str) or not title.strip():
            return _cors(jsonify({"error": "titleが必要です"}), 400)

        project = os.getenv("COSENSE_PROJECT", "").strip()
        sid = os.getenv("COSENSE_SID", "").strip()
        gyazo_token = os.getenv("GYAZO_ACCESS_TOKEN", "").strip()
        if not project or not sid or not gyazo_token:
            return _cors(jsonify({"error": "必要な環境変数が未設定です"}), 500)

        try:
            results = asyncio.run(
                refactor_target_pages(
                    BlueArchiveWikiClient(),
                    GyazoClient(gyazo_token),
                    TacticalChallengeCosenseClient(project=project, sid=sid),
                    target_title=title.strip(),
                )
            )
        except ValueError as error:
            return _cors(jsonify({"error": str(error)}), 400)
        except Exception as error:
            return _cors(jsonify({"error": str(error)}), 500)

        result = results[0]
        return _cors(
            jsonify(
                {
                    "title": result.title,
                    "changed_lines": result.changed_lines,
                    "created_icons": len(result.created_icons),
                }
            )
        )

    return blueprint


def _cors(response, status: int | None = None):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    if status is not None:
        response.status_code = status
    return response
