"""Telegram linking endpoints for the personal account."""

from flask import Blueprint, g, jsonify

from config import Config
from models.notifications import (
    create_telegram_link_code,
    deactivate_telegram_link,
    get_telegram_link_for_user,
)
from services.telegram_api import get_bot_username

telegram_lk_bp = Blueprint("telegram_lk", __name__)


@telegram_lk_bp.get("/telegram")
def get_telegram_status():
    link = get_telegram_link_for_user(g.db, g.current_user_id)
    return jsonify(
        {
            "success": True,
            "linked": link is not None,
            "telegram_username": (link["telegram_username"] if link else None),
            "linked_at": (link["linked_at"] if link else None),
            "bot_username": get_bot_username(Config.TELEGRAM_BOT_TOKEN),
            "bot_enabled": bool(Config.TELEGRAM_BOT_TOKEN),
        }
    ), 200


@telegram_lk_bp.post("/telegram/link-code")
def create_link_code():
    if not Config.TELEGRAM_BOT_TOKEN:
        return jsonify({"success": False, "error": "telegram bot is not configured"}), 503

    try:
        code, expires_at = create_telegram_link_code(
            g.db,
            g.current_user_id,
            Config.SECRET_KEY,
        )
    except Exception:
        return jsonify({"success": False, "error": "could not create link code"}), 500

    bot_username = get_bot_username(Config.TELEGRAM_BOT_TOKEN) or Config.TELEGRAM_BOT_USERNAME
    if not bot_username:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "telegram bot username is not available",
                }
            ),
            503,
        )

    telegram_url = f"https://t.me/{bot_username}?start={code}"
    return jsonify(
        {
            "success": True,
            "code": code,
            "expires_at": expires_at,
            "bot_username": bot_username,
            "telegram_url": telegram_url,
            "instruction": f"/start {code}",
        }
    ), 200


@telegram_lk_bp.delete("/telegram")
def unlink_telegram():
    deactivated = deactivate_telegram_link(g.db, g.current_user_id)
    return jsonify({"success": True, "unlinked": deactivated}), 200
