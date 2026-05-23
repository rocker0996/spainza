"""Read-only message audit API for management (level 1)."""

from functools import wraps

from flask import Blueprint, g, jsonify, request

from models.message import Message
from models.user import (
    get_all_users,
    get_role_definition,
    get_role_permissions,
    get_user_by_id,
    normalize_role_key,
)

admin_messages_bp = Blueprint("admin_messages", __name__)


def _require_management_audit():
    if not g.current_user_id:
        return jsonify({"success": False, "error": "unauthorized"}), 401

    viewer = get_user_by_id(g.db, int(g.current_user_id))
    if not viewer:
        return jsonify({"success": False, "error": "user not found"}), 404

    permissions = get_role_permissions(normalize_role_key(viewer["role_key"] or ""))
    if "full_access" not in permissions:
        return jsonify({"success": False, "error": "access denied"}), 403

    return None


def management_audit_required(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        denied = _require_management_audit()
        if denied is not None:
            return denied
        return handler(*args, **kwargs)

    return wrapper


def _parse_conversation_id(conversation_id: str):
    parts = (conversation_id or "").split("_")
    if len(parts) != 3 or parts[0] != "conv":
        return None
    try:
        return int(parts[1]), int(parts[2])
    except ValueError:
        return None


def _format_user_row(row) -> dict:
    role_key = normalize_role_key(row["role_key"] or "")
    role_data = get_role_definition(role_key)
    display_id = (row["display_id"] or "").strip() or None
    return {
        "id": row["id"],
        "display_id": display_id,
        "name": row["name"] or "",
        "email": row["email"] or "",
        "avatar": row["avatar"] or "",
        "role": {
            "key": role_data["key"],
            "level": role_data["level"],
            "name_ru": role_data["name_ru"],
        },
    }


def _serialize_audit_messages(messages: list[dict]) -> list[dict]:
    serialized = []
    for msg in (messages or []):
        payload = dict(msg)
        message_id = int(payload.get("id", 0) or 0)
        image_path = payload.pop("image_path", None)
        file_path = payload.pop("file_path", None)
        payload["image_url"] = (
            f"/api/messages/{message_id}/image" if message_id > 0 and image_path else None
        )
        payload["file_url"] = (
            f"/api/messages/{message_id}/file" if message_id > 0 and file_path else None
        )
        serialized.append(payload)
    return serialized


@admin_messages_bp.get("/api/admin/messages/users")
@management_audit_required
def list_audit_users():
    """All users for subject picker (management only)."""
    users_data = []
    for row in get_all_users(g.db):
        users_data.append(_format_user_row(row))

    return jsonify({"success": True, "users": users_data}), 200


@admin_messages_bp.get("/api/admin/messages/users/<int:subject_user_id>/conversations")
@management_audit_required
def list_subject_conversations(subject_user_id: int):
    subject = get_user_by_id(g.db, subject_user_id)
    if not subject:
        return jsonify({"success": False, "error": "user not found"}), 404

    conversations = Message.get_conversations_for_user_audit(subject_user_id)
    return jsonify(
        {
            "success": True,
            "subject": _format_user_row(subject),
            "conversations": conversations,
        }
    ), 200


@admin_messages_bp.get("/api/admin/messages/conversations/<conversation_id>/messages")
@management_audit_required
def get_conversation_messages_audit(conversation_id: str):
    subject_user_id = request.args.get("subject_user_id", type=int)
    if not subject_user_id:
        return jsonify({"success": False, "error": "subject_user_id is required"}), 400

    parsed = _parse_conversation_id(conversation_id)
    if not parsed:
        return jsonify({"success": False, "error": "invalid conversation id"}), 400

    user1_id, user2_id = parsed
    if subject_user_id not in (user1_id, user2_id):
        return jsonify({"success": False, "error": "subject not in conversation"}), 403

    subject = get_user_by_id(g.db, subject_user_id)
    if not subject:
        return jsonify({"success": False, "error": "user not found"}), 404

    other_user_id = user2_id if subject_user_id == user1_id else user1_id
    other = get_user_by_id(g.db, other_user_id)
    if not other:
        return jsonify({"success": False, "error": "counterparty not found"}), 404

    messages = Message.get_messages_for_audit(conversation_id, limit=500)

    return jsonify(
        {
            "success": True,
            "conversation_id": conversation_id,
            "subject": _format_user_row(subject),
            "other_user": _format_user_row(other),
            "messages": _serialize_audit_messages(messages),
        }
    ), 200
