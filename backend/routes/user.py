"""User profile routes."""

from flask import Blueprint, g, jsonify, request
from models.user import (
    ROLE_DEFINITIONS,
    can_assign_role,
    get_assignable_roles,
    get_role_definition,
    get_user_by_id,
    normalize_role_key,
    update_user_role,
)

user_bp = Blueprint("user", __name__)


@user_bp.get("/roles/assignable")
def list_assignable_roles():
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    current_role_key = normalize_role_key(current_user["role_key"] or "")
    roles = get_assignable_roles(current_role_key)
    return (
        jsonify(
            {
                "success": True,
                "roles": [
                    {
                        "key": role["key"],
                        "level": role["level"],
                        "name_ru": role["name_ru"],
                        "description_ru": role["description_ru"],
                    }
                    for role in roles
                ],
            }
        ),
        200,
    )


@user_bp.patch("/users/<int:target_user_id>/role")
def change_user_role(target_user_id: int):
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    # Запрет на изменение собственной роли
    if target_user_id == g.current_user_id:
        return jsonify({"success": False, "error": "cannot change own role"}), 403

    payload = request.get_json(silent=True) or {}
    requested_role_key = (payload.get("role_key") or "").strip()
    if not requested_role_key:
        return jsonify({"success": False, "error": "role_key is required"}), 400
    if requested_role_key not in ROLE_DEFINITIONS:
        return jsonify({"success": False, "error": "unknown role"}), 400

    actor_role_key = normalize_role_key(current_user["role_key"] or "")
    if not can_assign_role(actor_role_key, requested_role_key):
        return jsonify({"success": False, "error": "forbidden"}), 403

    target_user = get_user_by_id(g.db, target_user_id)
    if not target_user:
        return jsonify({"success": False, "error": "target user not found"}), 404

    role_changed = update_user_role(g.db, target_user_id, requested_role_key)
    if not role_changed:
        return jsonify({"success": False, "error": "role was not updated"}), 400

    role_data = get_role_definition(requested_role_key)
    return (
        jsonify(
            {
                "success": True,
                "user_id": target_user_id,
                "role": {
                    "key": role_data["key"],
                    "level": role_data["level"],
                    "name_ru": role_data["name_ru"],
                    "description_ru": role_data["description_ru"],
                },
            }
        ),
        200,
    )

