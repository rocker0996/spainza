"""Protected personal-account routes."""

import json
import os
import hashlib
from sqlite3 import IntegrityError

from flask import Blueprint, g, jsonify, request, send_file
from config import Config
from models.security_log import add_security_log, get_security_logs_for_user
from models.user import (
    delete_user_by_id,
    get_assignable_roles,
    get_assignable_visa_types,
    get_assignable_case_template_visa_types,
    can_assign_visa_type,
    can_manage_case_template_visa,
    get_user_auth_by_id,
    get_role_definition,
    get_role_permissions,
    get_user_by_id,
    is_portal_staff_role,
    normalize_role_key,
    update_user_password,
    update_user_profile,
    update_user_role,
    get_all_users,
    get_users_by_role_level,
    get_clients_for_manager,
    resolve_payload_client_user_id,
    normalize_public_display_id_value,
    get_internal_user_id_by_display_id,
    is_client_assignable_staff_role,
)
from models.case_data import (
    case_data_flag_is_true,
    count_sent_document_requests,
    get_case_data_by_user_id,
    mark_document_requests_sent,
    merge_document_requests_preserve_sent,
    upsert_case_data,
)
from services.case_template_apply import (
    materialize_case_from_template_if_needed,
    resolve_template_owner_id,
)
from models.case_template import (
    get_template_for_manager,
    list_templates_for_manager,
    upsert_template_for_manager,
)
from models.case_history import (
    add_history_entry,
    get_case_history,
)
from models.document import (
    count_rejected_documents_for_user,
    get_pending_document_counts_for_users,
)
from models.message import Message
from models.manager_moderator import (
    get_users_for_moderator,
    is_manager_role_key,
    is_moderator_role_key,
    moderator_may_access_user,
    viewer_uses_moderator_scoped_user_list,
)
from services.team_assignment import (
    add_team_member,
    expected_member_roles_for_assignment_kind,
    get_primary_manager_id_for_client,
    get_team_members_for_user,
    member_role_allowed_for_assignment_kind,
    remove_team_member,
    team_assignment_kind_for_target,
)
from services.file_service import FileService
from services.manager_client_assign import (
    ensure_manager_invite_token,
    should_sync_manager_clients,
    sync_manager_clients_from_case_manager_id,
    try_assign_client_to_manager,
)
from utils.security import hash_password, is_valid_email, is_valid_password, verify_password

lk_bp = Blueprint("lk", __name__)


def _request_ip() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.remote_addr or "").strip()


def _case_archive_file_id(user_id: int, archive_file_path: str | None) -> str | None:
    if not archive_file_path:
        return None
    digest = hashlib.sha256(str(archive_file_path).encode("utf-8")).hexdigest()[:12]
    return f"case_archive_{int(user_id)}_{digest}"


def _case_archive_download_url(user_id: int, archive_file_path: str | None) -> str | None:
    if not archive_file_path:
        return None
    return f"/api/case-data/{int(user_id)}/archive/download"


def _portal_support_user_row(connection):
    """Аккаунт поддержки из PORTAL_SUPPORT_USER_ID (для чата и превью на главной)."""
    row = get_user_by_id(connection, Config.PORTAL_SUPPORT_USER_ID)
    return row if row else None


def _assigned_manager_payload(connection, client_user_id: int) -> dict | None:
    """Первый закреплённый менеджер клиента (виден как персональный)."""
    mid = get_primary_manager_id_for_client(connection, client_user_id)
    if mid is None:
        case = get_case_data_by_user_id(connection, client_user_id)
        mid = case.get("manager_id") if case else None
    if mid is None:
        return None
    try:
        mid_int = int(mid)
    except (TypeError, ValueError):
        return None
    if mid_int <= 0:
        return None
    mgr = get_user_by_id(connection, mid_int)
    if not mgr:
        return None
    mgr_role_key = normalize_role_key(mgr["role_key"] or "")
    mgr_role_data = get_role_definition(mgr_role_key)
    return {
        "id": mgr["id"],
        "name": mgr["name"] or "",
        "email": mgr["email"] or "",
        "avatar": mgr["avatar"] or "",
        "display_id": (mgr["display_id"] or "").strip() or None,
        "role": {
            "key": mgr_role_data["key"],
            "name_ru": mgr_role_data["name_ru"],
        },
    }


def _entity_key_from_dict(row: dict, index: int) -> tuple[str, object]:
    """Стабильный ключ строки (id из JSON или позиция)."""
    sid = row.get("id")
    if sid is not None and sid != "":
        try:
            return ("id", int(sid))
        except (TypeError, ValueError):
            return ("id", str(sid))
    return ("idx", index)


def _map_rows_by_key(rows: list) -> dict[tuple[str, object], dict]:
    out: dict[tuple[str, object], dict] = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        out[_entity_key_from_dict(row, i)] = row
    return out


def _case_history_timeline_details(old_steps: list, new_steps: list) -> str:
    """Человекочитаемое описание изменений графика заявки (для case_history.details)."""
    old_list = [x for x in (old_steps or []) if isinstance(x, dict)]
    new_list = [x for x in (new_steps or []) if isinstance(x, dict)]
    status_ru = {
        "completed": "завершено",
        "active": "активно",
        "pending": "ожидание",
    }

    def title_of(s: dict) -> str:
        t = str(s.get("title") or "").strip()
        return (t or "Без названия")[:180]

    def status_label(s: dict) -> str:
        st = str(s.get("status") or "pending").strip().lower()
        return status_ru.get(st, st or "—")

    old_map = _map_rows_by_key(old_list)
    new_map = _map_rows_by_key(new_list)
    old_keys = set(old_map.keys())
    new_keys = set(new_map.keys())

    parts: list[str] = [
        f"В графике сейчас {len(new_list)} шаг(ов); до сохранения было {len(old_list)}."
    ]

    for k in sorted(new_keys - old_keys, key=lambda x: (x[0], str(x[1]))):
        parts.append(f"Добавлен шаг «{title_of(new_map[k])}» (статус: {status_label(new_map[k])}).")

    for k in sorted(old_keys - new_keys, key=lambda x: (x[0], str(x[1]))):
        parts.append(f"Удалён шаг «{title_of(old_map[k])}».")

    for k in sorted(old_keys & new_keys, key=lambda x: (x[0], str(x[1]))):
        o, n = old_map[k], new_map[k]
        t_o, t_n = title_of(o), title_of(n)
        d_o = str(o.get("description") or "").strip()
        d_n = str(n.get("description") or "").strip()
        s_o, s_n = status_label(o), status_label(n)
        bits: list[str] = []
        if t_o != t_n:
            bits.append(f"название: «{t_o[:100]}» → «{t_n[:100]}»")
        if d_o != d_n:
            bits.append("текст описания и сроков изменён")
        if s_o != s_n:
            bits.append(f"статус: {s_o} → {s_n}")
        if bits:
            parts.append(f"Шаг «{t_n}»: {', '.join(bits)}.")

    order_old = [_entity_key_from_dict(s, i) for i, s in enumerate(old_list)]
    order_new = [_entity_key_from_dict(s, i) for i, s in enumerate(new_list)]
    if old_keys == new_keys and order_old != order_new:
        parts.append("Изменён порядок шагов (перетаскивание).")

    text = "\n".join(parts)
    return text[:2000]


def _case_history_document_requests_details(old_docs: list, new_docs: list) -> str:
    """Человекочитаемое описание изменений запросов документов."""
    old_list = [x for x in (old_docs or []) if isinstance(x, dict)]
    new_list = [x for x in (new_docs or []) if isinstance(x, dict)]
    priority_ru = {
        "urgent": "срочно",
        "normal": "обычный приоритет",
        "optional": "необязательно",
    }

    def name_of(s: dict) -> str:
        n = str(s.get("name") or "").strip()
        return (n or "Без названия")[:180]

    def pr_label(s: dict) -> str:
        p = str(s.get("priority") or "normal").strip().lower()
        return priority_ru.get(p, p or "—")

    old_map = _map_rows_by_key(old_list)
    new_map = _map_rows_by_key(new_list)
    old_keys = set(old_map.keys())
    new_keys = set(new_map.keys())

    parts: list[str] = [
        f"В чек-листе {len(new_list)} позиций; до сохранения было {len(old_list)}."
    ]

    for k in sorted(new_keys - old_keys, key=lambda x: (x[0], str(x[1]))):
        nm = name_of(new_map[k])
        custom = " (пользовательский запрос)" if not new_map[k].get("isDefault") else ""
        parts.append(f"Добавлен запрос «{nm}»{custom}.")

    for k in sorted(old_keys - new_keys, key=lambda x: (x[0], str(x[1]))):
        parts.append(f"Удалён запрос «{name_of(old_map[k])}».")

    for k in sorted(old_keys & new_keys, key=lambda x: (x[0], str(x[1]))):
        o, n = old_map[k], new_map[k]
        nm = name_of(n)
        bits: list[str] = []
        if name_of(o) != name_of(n):
            bits.append(f"название: «{name_of(o)[:80]}» → «{name_of(n)[:80]}»")
        desc_o = str(o.get("description") or "").strip()
        desc_n = str(n.get("description") or "").strip()
        if desc_o != desc_n:
            bits.append("описание требований изменено")
        pr_o, pr_n = pr_label(o), pr_label(n)
        if pr_o != pr_n:
            bits.append(f"приоритет: {pr_o} → {pr_n}")

        sent_o, sent_n = bool(o.get("sent")), bool(n.get("sent"))
        if sent_o != sent_n:
            if sent_n:
                bits.append("запрос отмечен как отправленный клиенту")
            else:
                bits.append("запрос отозван (снова доступен для правок и повторной отправки)")

        chk_o, chk_n = bool(o.get("checked")), bool(n.get("checked"))
        if chk_o != chk_n and not sent_n:
            bits.append("включена отметка к отправке" if chk_n else "снята отметка к отправке")

        if bits:
            parts.append(f"«{nm}»: {', '.join(bits)}.")

    text = "\n".join(parts)
    return text[:2000]


@lk_bp.get("/lk/session")
def lk_session():
    return jsonify({"success": True, "user_id": g.current_user_id}), 200


def _users_list_for_viewer(connection, viewer_id: int, role_key: str, permissions: set[str]) -> list:
    """Users visible on clients page for the current viewer (same rules as GET /users)."""
    role_data = get_role_definition(role_key)

    if "full_access" in permissions or "view_all_users" in permissions:
        return get_all_users(connection)
    if "view_lower_users" in permissions:
        min_level_to_show = float(role_data["level"]) + 1
        return get_users_by_role_level(connection, str(min_level_to_show))
    if "view_assignable_users" in permissions:
        if viewer_uses_moderator_scoped_user_list(role_key, permissions):
            return get_users_for_moderator(connection, viewer_id)
        assignable_roles = get_assignable_roles(role_key)
        if assignable_roles:
            min_level = min(float(r["level"]) for r in assignable_roles)
            return get_users_by_role_level(connection, str(min_level))
        return []
    if "view_assigned_clients" in permissions:
        return get_clients_for_manager(connection, viewer_id)
    return []


@lk_bp.get("/lk/nav-badges")
def lk_nav_badges():
    """Lightweight nav counters (messages, documents, clients)."""
    user = get_user_by_id(g.db, g.current_user_id)
    if not user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(user["role_key"] or "")
    permissions = set(get_role_permissions(role_key))

    unread_count = int(Message.get_unread_count(g.current_user_id) or 0)

    document_request_count = 0
    document_rejected_count = 0
    if not is_portal_staff_role(role_key):
        document_rejected_count = count_rejected_documents_for_user(g.db, g.current_user_id)
        case_data = get_case_data_by_user_id(g.db, g.current_user_id)
        document_request_count = count_sent_document_requests(case_data)

    clients_with_pending = 0
    view_permissions = {
        "full_access",
        "view_all_users",
        "view_lower_users",
        "view_assignable_users",
        "view_assigned_clients",
    }
    if view_permissions & permissions:
        users_list = _users_list_for_viewer(g.db, g.current_user_id, role_key, permissions)
        if users_list:
            pending_counts = get_pending_document_counts_for_users(
                g.db,
                [int(u["id"]) for u in users_list],
            )
            clients_with_pending = sum(
                1 for u in users_list if pending_counts.get(int(u["id"]), 0) > 0
            )

    return jsonify(
        {
            "success": True,
            "unread_count": unread_count,
            "document_request_count": document_request_count,
            "document_rejected_count": document_rejected_count,
            "clients_with_pending": clients_with_pending,
        }
    ), 200


@lk_bp.get("/user")
def get_current_user():
    user = get_user_by_id(g.db, g.current_user_id)
    if not user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(user["role_key"] or "")
    role_data = get_role_definition(role_key)

    support_row = _portal_support_user_row(g.db)
    support_display_id = (
        (support_row["display_id"] or "").strip() if support_row else ""
    ) or None
    support_user_id = int(support_row["id"]) if support_row else None

    return (
        jsonify(
            {
                "success": True,
                "id": user["id"],
                "name": user["name"] or "",
                "email": user["email"] or "",
                "created_at": user["created_at"] or "",
                "avatar": user["avatar"] or "",
                "phone": user["phone"] or "",
                "main_goal": user["main_goal"] or "",
                "locale": (user["locale"] or "ru").strip() or "ru",
                "application_type": user["application_type"] or "vnj_investment",
                "current_stage": user["current_stage"] or "consultation",
                "notifications": {
                    "email": bool(user["notify_email"]),
                    "sms": bool(user["notify_sms"]),
                    "whatsapp": bool(user["notify_whatsapp"]),
                },
                "role": {
                    "key": role_data["key"],
                    "level": role_data["level"],
                    "name_ru": role_data["name_ru"],
                    "description_ru": role_data["description_ru"],
                },
                "permissions": get_role_permissions(role_key),
                "assignable_roles": [
                    {
                        "key": role["key"],
                        "level": role["level"],
                        "name_ru": role["name_ru"],
                        "description_ru": role["description_ru"],
                    }
                    for role in get_assignable_roles(role_key)
                ],
                "assignable_visa_types": get_assignable_visa_types(role_key),
                "assigned_manager": _assigned_manager_payload(g.db, int(user["id"])),
                "display_id": (user["display_id"] or "").strip() or None,
                "support_display_id": support_display_id,
                "support_user_id": support_user_id,
            }
        ),
        200,
    )


@lk_bp.patch("/user")
def update_current_user_profile():
    user = get_user_by_id(g.db, g.current_user_id)
    if not user:
        return jsonify({"success": False, "error": "user not found"}), 404

    payload = request.get_json(silent=True) or {}

    name = str(payload.get("name") or "").strip()
    email = str(payload.get("email") or "").strip().lower()
    avatar = str(payload.get("avatar") or "").strip()
    phone = str(payload.get("phone") or "").strip()
    main_goal = str(payload.get("main_goal") or "").strip()
    locale = str(payload.get("locale") or "ru").strip().lower()
    notifications = payload.get("notifications") if isinstance(payload.get("notifications"), dict) else {}

    if not email:
        return jsonify({"success": False, "error": "email is required"}), 400
    if not is_valid_email(email):
        return jsonify({"success": False, "error": "invalid email"}), 400
    if locale not in {"ru", "en"}:
        locale = "ru"

    normalized_payload = {
        "name": name,
        "email": email,
        "avatar": avatar,
        "phone": phone,
        "main_goal": main_goal,
        "locale": locale,
        "notify_email": bool(notifications.get("email", bool(user["notify_email"]))),
        "notify_sms": bool(notifications.get("sms", bool(user["notify_sms"]))),
        "notify_whatsapp": bool(notifications.get("whatsapp", bool(user["notify_whatsapp"]))),
    }

    try:
        updated = update_user_profile(g.db, g.current_user_id, normalized_payload)
    except IntegrityError:
        return jsonify({"success": False, "error": "email already exists"}), 409

    if not updated:
        return jsonify({"success": False, "error": "profile was not updated"}), 400

    add_security_log(
        g.db,
        g.current_user_id,
        "profile_updated",
        "Профиль обновлен",
        details="Изменены основные данные профиля или уведомления.",
        ip_address=_request_ip(),
    )
    return jsonify({"success": True}), 200


@lk_bp.patch("/user/password")
def update_current_user_password():
    user = get_user_auth_by_id(g.db, g.current_user_id)
    if not user:
        return jsonify({"success": False, "error": "user not found"}), 404

    payload = request.get_json(silent=True) or {}
    current_password = str(payload.get("current_password") or "")
    new_password = str(payload.get("new_password") or "")

    if not current_password or not new_password:
        return jsonify({"success": False, "error": "current and new passwords are required"}), 400
    if not verify_password(current_password, user["password_hash"]):
        add_security_log(
            g.db,
            g.current_user_id,
            "password_change_failed",
            "Неудачная попытка смены пароля",
            details="Указан неверный текущий пароль.",
            ip_address=_request_ip(),
        )
        return jsonify({"success": False, "error": "invalid current password"}), 400
    if not is_valid_password(new_password):
        return jsonify({"success": False, "error": "new password is too weak"}), 400

    updated = update_user_password(g.db, g.current_user_id, hash_password(new_password))
    if not updated:
        return jsonify({"success": False, "error": "password was not updated"}), 400

    add_security_log(
        g.db,
        g.current_user_id,
        "password_updated",
        "Пароль обновлен",
        details="Пароль успешно изменен в личном кабинете.",
        ip_address=_request_ip(),
    )
    return jsonify({"success": True}), 200


@lk_bp.get("/user/security-logs")
def get_current_user_security_logs():
    user = get_user_by_id(g.db, g.current_user_id)
    if not user:
        return jsonify({"success": False, "error": "user not found"}), 404

    rows = get_security_logs_for_user(g.db, g.current_user_id, limit=50)
    logs = [
        {
            "id": row["id"],
            "event_type": row["event_type"] or "",
            "event_title": row["event_title"] or "",
            "details": row["details"] or "",
            "ip_address": row["ip_address"] or "",
            "created_at": row["created_at"] or "",
        }
        for row in rows
    ]
    return jsonify({"success": True, "logs": logs}), 200


@lk_bp.delete("/user")
def delete_current_user():
    add_security_log(
        g.db,
        g.current_user_id,
        "account_deleted",
        "Аккаунт удален",
        details="Пользователь удалил аккаунт через настройки.",
        ip_address=_request_ip(),
    )
    deleted = delete_user_by_id(g.db, g.current_user_id)
    if not deleted:
        return jsonify({"success": False, "error": "user not found"}), 404
    return jsonify({"success": True}), 200


def _can_assign_client_link(permissions: list[str]) -> bool:
    """Кто может получить invite-ссылку и закрепить клиента (как на странице clients)."""
    return bool(
        "full_access" in permissions
        or "view_all_users" in permissions
        or "view_lower_users" in permissions
        or "view_assignable_users" in permissions
        or "view_assigned_clients" in permissions
        or "assign_client_roles" in permissions
    )


def _manager_has_assigned_client(manager_user_id: int, client_user_id: int) -> bool:
    row = g.db.execute(
        "SELECT 1 FROM manager_clients WHERE manager_id = ? AND client_id = ?",
        (manager_user_id, client_user_id),
    ).fetchone()
    return bool(row)


def _viewer_may_access_client_case_data(
    connection, viewer_user_id: int, client_user_id: int
) -> bool:
    """Доступ к кейсу клиента: согласован с GET /users/<id> + линия staff (communicate/respond)."""
    current_user = get_user_by_id(connection, viewer_user_id)
    if current_user:
        viewer_role_key = normalize_role_key(current_user["role_key"] or "")
        if is_manager_role_key(viewer_role_key) and viewer_user_id == client_user_id:
            return False
    if viewer_user_id == client_user_id:
        return True
    if not current_user:
        return False
    role_key = normalize_role_key(current_user["role_key"] or "")
    role_data = get_role_definition(role_key)
    permissions = get_role_permissions(role_key)

    target_user = get_user_by_id(connection, client_user_id)
    if not target_user:
        return False
    target_role_key = normalize_role_key(target_user["role_key"] or "")
    target_role_data = get_role_definition(target_role_key)

    if "full_access" in permissions or "view_all_users" in permissions:
        return True
    if "communicate_with_clients" in permissions or "respond_to_applications" in permissions:
        return True
    if "view_lower_users" in permissions:
        return float(target_role_data["level"]) >= float(role_data["level"])
    if "view_assignable_users" in permissions:
        if viewer_uses_moderator_scoped_user_list(role_key, permissions):
            return moderator_may_access_user(connection, viewer_user_id, client_user_id)
        assignable_roles = get_assignable_roles(role_key)
        assignable_keys = [r["key"] for r in assignable_roles]
        return target_role_key in assignable_keys
    if "view_assigned_clients" in permissions:
        row = connection.execute(
            "SELECT 1 FROM manager_clients WHERE manager_id = ? AND client_id = ?",
            (viewer_user_id, client_user_id),
        ).fetchone()
        return bool(row)
    return False


def _viewer_can_see_user_profile_in_directory(
    connection, viewer_user_id: int, target_user_id: int
) -> tuple[bool, str]:
    """Те же правила, что GET /users/<id>: список/карточка пользователя в каталоге персонала."""
    current_user = get_user_by_id(connection, viewer_user_id)
    if not current_user:
        return False, "user not found"

    role_key = normalize_role_key(current_user["role_key"] or "")
    role_data = get_role_definition(role_key)
    permissions = get_role_permissions(role_key)

    has_view_permission = (
        "full_access" in permissions
        or "view_all_users" in permissions
        or "view_lower_users" in permissions
        or "view_assignable_users" in permissions
        or "view_assigned_clients" in permissions
    )
    if not has_view_permission:
        return False, "access denied"

    target_user = get_user_by_id(connection, target_user_id)
    if not target_user:
        return False, "user not found"

    target_role_key = normalize_role_key(target_user["role_key"] or "")
    target_role_data = get_role_definition(target_role_key)

    can_view = False
    if "full_access" in permissions or "view_all_users" in permissions:
        can_view = True
    elif "view_lower_users" in permissions:
        can_view = float(target_role_data["level"]) >= float(role_data["level"])
    elif "view_assignable_users" in permissions:
        if viewer_uses_moderator_scoped_user_list(role_key, permissions):
            can_view = moderator_may_access_user(connection, viewer_user_id, target_user_id)
        else:
            can_view = float(target_role_data["level"]) >= float(role_data["level"])
    elif "view_assigned_clients" in permissions:
        row = connection.execute(
            "SELECT 1 FROM manager_clients WHERE manager_id = ? AND client_id = ?",
            (viewer_user_id, target_user_id),
        ).fetchone()
        can_view = bool(row)

    if not can_view:
        return False, "access denied to this user"
    return True, ""


def _lookup_allowed_for_case_assignment(
    connection, viewer_user_id: int, for_case_user_id: int, lookup_user_id: int
) -> bool:
    """Кого можно подставить в «Работает над кейсом» при редактировании кейса."""
    for_case_user = get_user_by_id(connection, for_case_user_id)
    lookup_user = get_user_by_id(connection, lookup_user_id)
    if not for_case_user or not lookup_user:
        return False
    for_case_role = normalize_role_key(for_case_user["role_key"] or "")
    lookup_role = normalize_role_key(lookup_user["role_key"] or "")

    kind = team_assignment_kind_for_target(for_case_role)
    if kind == "manager_moderators":
        return is_moderator_role_key(lookup_role)
    if kind == "moderator_managers":
        return is_manager_role_key(lookup_role)
    if not kind:
        return False
    return member_role_allowed_for_assignment_kind(kind, lookup_role)


def _json_user_detail_for_staff_view(target_user) -> dict:
    target_role_key = normalize_role_key(target_user["role_key"] or "")
    target_role_data = get_role_definition(target_role_key)
    return {
        "id": target_user["id"],
        "display_id": (target_user["display_id"] or "").strip() or None,
        "name": target_user["name"] or "",
        "email": target_user["email"] or "",
        "avatar": target_user["avatar"] or "",
        "phone": target_user["phone"] or "",
        "created_at": target_user["created_at"] or "",
        "main_goal": target_user["main_goal"] or "",
        "locale": target_user["locale"] or "ru",
        "application_type": target_user["application_type"] or "",
        "current_stage": target_user["current_stage"] or "",
        "role": {
            "key": target_role_data["key"],
            "level": target_role_data["level"],
            "name_ru": target_role_data["name_ru"],
            "description_ru": target_role_data["description_ru"],
        },
    }


@lk_bp.get("/lk/manager-invite")
def get_manager_invite_link():
    """Токен и относительный путь для ссылки приглашения клиента."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(current_user["role_key"] or "")
    permissions = get_role_permissions(role_key)
    if not _can_assign_client_link(permissions):
        return jsonify({"success": False, "error": "access denied"}), 403
    if not is_portal_staff_role(role_key):
        return jsonify({"success": False, "error": "access denied"}), 403

    token = ensure_manager_invite_token(g.db, g.current_user_id)
    if not token:
        return jsonify({"success": False, "error": "could not create invite token"}), 400

    path = f"/frontend/login.html?invite={token}"
    base = (request.host_url or "").rstrip("/")
    full_url = f"{base}{path}" if base else path
    return (
        jsonify(
            {
                "success": True,
                "invite_token": token,
                "invite_path": path,
                "invite_url": full_url,
            }
        ),
        200,
    )


@lk_bp.post("/lk/clients/assign-by-id")
def assign_client_by_id():
    """Закрепить клиента по ID за текущим менеджером (manager_clients + персональный менеджер в кейсе)."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(current_user["role_key"] or "")
    permissions = get_role_permissions(role_key)
    if not _can_assign_client_link(permissions):
        return jsonify({"success": False, "error": "access denied"}), 403

    messages = {
        "client_not_found": "Пользователь с таким ID не найден.",
        "target_not_client": "Указанный пользователь не является клиентом.",
        "personal_manager_taken": (
            "Клиент занят другим менеджером. Проверьте правильность ID или обратитесь к модератору."
        ),
        "invalid_ids": "Некорректный ID.",
        "missing_client_id": "Укажите ID клиента.",
        "save_failed": "Не удалось сохранить данные кейса.",
    }

    payload = request.get_json(silent=True) or {}
    client_id, resolve_err = resolve_payload_client_user_id(g.db, payload)
    if resolve_err == "missing_client_id":
        return (
            jsonify(
                {
                    "success": False,
                    "error": "missing_client_id",
                    "message_ru": messages["missing_client_id"],
                }
            ),
            400,
        )
    if resolve_err == "invalid_ids":
        return (
            jsonify(
                {
                    "success": False,
                    "error": "invalid_ids",
                    "message_ru": messages["invalid_ids"],
                }
            ),
            400,
        )
    if resolve_err == "client_not_found":
        return (
            jsonify(
                {
                    "success": False,
                    "error": "client_not_found",
                    "message_ru": messages["client_not_found"],
                }
            ),
            404,
        )

    ok, code = try_assign_client_to_manager(g.db, g.current_user_id, client_id)
    if ok:
        add_security_log(
            g.db,
            g.current_user_id,
            "client_assigned",
            f"Клиент #{client_id} закреплён за менеджером",
            details="Добавление по ID со страницы клиентов.",
            ip_address=_request_ip(),
        )
        return jsonify({"success": True}), 200

    status = 404 if code == "client_not_found" else 400
    if code == "personal_manager_taken":
        status = 409
    return (
        jsonify(
            {
                "success": False,
                "error": code,
                "message_ru": messages.get(code, "Ошибка привязки клиента."),
            }
        ),
        status,
    )


@lk_bp.get("/users")
def get_users_list():
    """Get list of users based on current user's permissions."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(current_user["role_key"] or "")
    role_data = get_role_definition(role_key)
    permissions = get_role_permissions(role_key)
    
    # Check if user has permission to view users
    has_view_permission = (
        "full_access" in permissions or
        "view_all_users" in permissions or
        "view_lower_users" in permissions or
        "view_assignable_users" in permissions or
        "view_assigned_clients" in permissions
    )
    
    if not has_view_permission:
        return jsonify({"success": False, "error": "access denied"}), 403
    
    # Determine which users to show based on permissions
    users_list = []
    
    if "full_access" in permissions or "view_all_users" in permissions:
        # Management: sees all users (включая других management)
        users_list = get_all_users(g.db)
    elif "view_lower_users" in permissions:
        # Admin/Moderator: sees only users with level > their level (не видят равных по статусу)
        # Например, Admin (level=2) видит только level > 2 (moderator=3, manager=4, clients=5+)
        min_level_to_show = float(role_data["level"]) + 1
        users_list = get_users_by_role_level(g.db, str(min_level_to_show))
    elif "view_assignable_users" in permissions:
        if viewer_uses_moderator_scoped_user_list(role_key, permissions):
            users_list = get_users_for_moderator(g.db, g.current_user_id)
        else:
            assignable_roles = get_assignable_roles(role_key)
            if assignable_roles:
                min_level = min(float(r["level"]) for r in assignable_roles)
                users_list = get_users_by_role_level(g.db, str(min_level))
            else:
                users_list = []
    elif "view_assigned_clients" in permissions:
        # Manager: sees only assigned clients
        users_list = get_clients_for_manager(g.db, g.current_user_id)
    
    # Format response
    pending_counts_by_user = get_pending_document_counts_for_users(
        g.db,
        [user["id"] for user in users_list],
    )

    users_data = []
    for user in users_list:
        user_role_key = normalize_role_key(user["role_key"] or "")
        user_role_data = get_role_definition(user_role_key)
        
        # Load case data to get visa_type
        case_data = get_case_data_by_user_id(g.db, user["id"])
        visa_type = case_data.get("visa_type") if case_data else None
        target_date = (case_data.get("target_date") or "").strip() if case_data else ""

        users_data.append({
            "id": user["id"],
            "display_id": (user["display_id"] or "").strip() or None,
            "name": user["name"] or "",
            "email": user["email"] or "",
            "avatar": user["avatar"] or "",
            "phone": user["phone"] or "",
            "created_at": user["created_at"] or "",
            "visa_type": visa_type,
            "target_date": target_date,
            "pending_documents_count": pending_counts_by_user.get(user["id"], 0),
            "role": {
                "key": user_role_data["key"],
                "level": user_role_data["level"],
                "name_ru": user_role_data["name_ru"],
            }
        })
    
    return jsonify({
        "success": True,
        "users": users_data,
        "viewer_role": {
            "key": role_data["key"],
            "level": role_data["level"],
            "name_ru": role_data["name_ru"],
        },
        "viewer_permissions": permissions
    }), 200


@lk_bp.get("/users/lookup-by-display")
def lookup_user_by_display_for_case():
    """Разрешить менеджеру найти коллегу по публичному display_id при редактировании кейса."""
    for_case_user_id = request.args.get("for_case_user_id", type=int)
    if not for_case_user_id:
        return jsonify({"success": False, "error": "for_case_user_id is required"}), 400

    if not _viewer_may_access_client_case_data(g.db, g.current_user_id, for_case_user_id):
        return jsonify({"success": False, "error": "access denied"}), 403

    normalized = normalize_public_display_id_value(request.args.get("display_id", ""))
    if not normalized:
        return jsonify({"success": False, "error": "invalid display_id"}), 400

    target_id = get_internal_user_id_by_display_id(g.db, normalized)
    if target_id is None:
        return jsonify({"success": False, "error": "user not found"}), 404

    if not _lookup_allowed_for_case_assignment(
        g.db, g.current_user_id, for_case_user_id, target_id
    ):
        return jsonify({"success": False, "error": "access denied"}), 403

    target_user = get_user_by_id(g.db, target_id)
    return (
        jsonify({"success": True, "user": _json_user_detail_for_staff_view(target_user)}),
        200,
    )


@lk_bp.get("/lk/case-client/resolve")
def resolve_case_client_from_public_id():
    """По публичному номеру из ссылки (?client=AA1234) вернуть внутренний id при доступе к кейсу клиента."""
    normalized = normalize_public_display_id_value(request.args.get("client", ""))
    if not normalized:
        return jsonify({"success": False, "error": "client is required"}), 400
    uid = get_internal_user_id_by_display_id(g.db, normalized)
    if uid is None:
        return jsonify({"success": False, "error": "user not found"}), 404
    if not _viewer_may_access_client_case_data(g.db, g.current_user_id, uid):
        return jsonify({"success": False, "error": "access denied"}), 403
    return (
        jsonify({"success": True, "user_id": uid, "display_id": normalized}),
        200,
    )


@lk_bp.get("/users/<int:user_id>")
def get_user_by_id_endpoint(user_id: int):
    """Get specific user by ID (with permission check)."""
    ok, err = _viewer_can_see_user_profile_in_directory(g.db, g.current_user_id, user_id)
    if not ok:
        status = 404 if err == "user not found" else 403
        return jsonify({"success": False, "error": err}), status

    target_user = get_user_by_id(g.db, user_id)
    return (
        jsonify({"success": True, "user": _json_user_detail_for_staff_view(target_user)}),
        200,
    )


@lk_bp.get("/case-data/<int:user_id>")
def get_case_data(user_id: int):
    """Get case management data for a specific user."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    if not _viewer_may_access_client_case_data(g.db, g.current_user_id, user_id):
        return jsonify({"success": False, "error": "access denied"}), 403

    materialize_case_from_template_if_needed(
        g.db, user_id, fallback_viewer_id=g.current_user_id
    )

    target_user = get_user_by_id(g.db, user_id)
    target_role_key = (
        normalize_role_key(target_user["role_key"] or "") if target_user else ""
    )
    team_kind = team_assignment_kind_for_target(target_role_key)
    team_members = get_team_members_for_user(g.db, user_id)

    # Get case data
    case_data = get_case_data_by_user_id(g.db, user_id)
    
    if not case_data:
        default_visa = target_role_key or "user"
        empty_payload = {
            "user_id": user_id,
            "visa_type": default_visa,
            "target_date": None,
            "country": "",
            "archive_file_name": None,
            "archive_file_id": None,
            "archive_download_url": None,
            "timeline": [],
            "document_requests": [],
            "referral_id": None,
            "manager_id": get_primary_manager_id_for_client(g.db, user_id),
            "timeline_manual": False,
            "document_requests_manual": False,
            "team_assignment_kind": team_kind,
            "team_members": team_members,
        }
        return jsonify({
            "success": True,
            "case_data": empty_payload,
        }), 200
    
    response_case_data = dict(case_data)
    archive_file_path = response_case_data.pop("archive_file_path", None)
    response_case_data["archive_file_id"] = _case_archive_file_id(
        user_id, archive_file_path
    )
    response_case_data["archive_download_url"] = _case_archive_download_url(
        user_id, archive_file_path
    )
    response_case_data["team_assignment_kind"] = team_kind
    response_case_data["team_members"] = team_members
    if team_kind == "client_managers":
        response_case_data["manager_id"] = get_primary_manager_id_for_client(
            g.db, user_id
        )

    return jsonify({
        "success": True,
        "case_data": response_case_data
    }), 200


@lk_bp.post("/lk/case-team/<int:user_id>/add")
def add_case_team_member(user_id: int):
    """Добавить участника в «Работает над кейсом» (менеджер/модератор по типу цели)."""
    if not _viewer_may_access_client_case_data(g.db, g.current_user_id, user_id):
        return jsonify({"success": False, "error": "access denied"}), 403

    payload = request.get_json(silent=True) or {}
    member_id, resolve_err = resolve_payload_client_user_id(g.db, payload)
    if resolve_err:
        return jsonify({"success": False, "error": resolve_err}), 400

    target = get_user_by_id(g.db, user_id)
    if not target:
        return jsonify({"success": False, "error": "user_not_found"}), 404
    target_role = normalize_role_key(target["role_key"] or "")
    assignment_kind = team_assignment_kind_for_target(target_role)
    if not assignment_kind:
        return jsonify({"success": False, "error": "unsupported_target"}), 400

    member = get_user_by_id(g.db, member_id)
    if not member:
        return jsonify({"success": False, "error": "user_not_found"}), 404

    member_role = normalize_role_key(member["role_key"] or "")
    if not member_role_allowed_for_assignment_kind(assignment_kind, member_role):
        return (
            jsonify(
                {
                    "success": False,
                    "error": "invalid_member_role",
                    "assignment_kind": assignment_kind,
                    "member_role": member_role,
                    "member_display_id": (member["display_id"] or "").strip() or None,
                    "expected_roles": expected_member_roles_for_assignment_kind(
                        assignment_kind
                    ),
                }
            ),
            400,
        )

    try:
        ok, code = add_team_member(g.db, user_id, member_id)
    except Exception as exc:
        print(f"[case-team/add] add_team_member failed: {exc}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": "save_failed"}), 500

    if not ok:
        status = 404 if code == "user_not_found" else 400
        payload = {"success": False, "error": code}
        if code == "invalid_member_role" and member:
            payload["assignment_kind"] = assignment_kind
            payload["member_role"] = member_role
            payload["member_display_id"] = (member["display_id"] or "").strip() or None
            payload["expected_roles"] = expected_member_roles_for_assignment_kind(
                assignment_kind
            )
        return jsonify(payload), status

    target = get_user_by_id(g.db, user_id)
    member = get_user_by_id(g.db, member_id)
    if target and member:
        kind = team_assignment_kind_for_target(target["role_key"] or "")
        label = {
            "client_managers": "Назначен сотрудник",
            "manager_moderators": "Назначен модератор",
            "moderator_managers": "Назначен менеджер",
        }.get(kind or "", "Назначен сотрудник")
        add_history_entry(
            g.db,
            user_id,
            g.current_user_id,
            label,
            f"{member['name'] or member['email']} (ID: {member_id})",
        )

    try:
        team_members = get_team_members_for_user(g.db, user_id)
    except Exception as exc:
        print(f"[case-team/add] get_team_members_for_user failed: {exc}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": "save_failed"}), 500

    return jsonify(
        {
            "success": True,
            "team_members": team_members,
        }
    ), 200


@lk_bp.delete("/lk/case-team/<int:user_id>/<int:member_id>")
def remove_case_team_member(user_id: int, member_id: int):
    if not _viewer_may_access_client_case_data(g.db, g.current_user_id, user_id):
        return jsonify({"success": False, "error": "access denied"}), 403

    member = get_user_by_id(g.db, member_id)
    ok, code = remove_team_member(g.db, user_id, member_id)
    if not ok:
        return jsonify({"success": False, "error": code}), 400

    if member:
        target = get_user_by_id(g.db, user_id)
        kind = team_assignment_kind_for_target((target or {})["role_key"] or "") if target else ""
        label = {
            "client_managers": "Менеджер удален",
            "manager_moderators": "Модератор удалён",
            "moderator_managers": "Менеджер удален",
        }.get(kind or "", "Сотрудник снят")
        add_history_entry(
            g.db,
            user_id,
            g.current_user_id,
            label,
            f"{member['name'] or member['email']} (ID: {member_id})",
        )

    return jsonify(
        {
            "success": True,
            "team_members": get_team_members_for_user(g.db, user_id),
        }
    ), 200


@lk_bp.post("/case-data/<int:user_id>/document-requests/send")
def send_case_document_requests(user_id: int):
    """Mark selected document requests as sent (atomic, avoids full-case save races)."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    if not _viewer_may_access_client_case_data(g.db, g.current_user_id, user_id):
        return jsonify({"success": False, "error": "access denied"}), 403

    if not get_user_by_id(g.db, user_id):
        return jsonify({"success": False, "error": "target user not found"}), 404

    payload = request.get_json(silent=True) or {}
    raw_ids = payload.get("request_ids")
    if not isinstance(raw_ids, list) or not raw_ids:
        return jsonify({"success": False, "error": "request_ids required"}), 400

    parsed_ids: list[int] = []
    for raw_id in raw_ids:
        try:
            parsed_ids.append(int(raw_id))
        except (TypeError, ValueError):
            continue
    if not parsed_ids:
        return jsonify({"success": False, "error": "request_ids required"}), 400

    ok, requests, updated = mark_document_requests_sent(g.db, user_id, parsed_ids)
    if not ok:
        return jsonify({"success": False, "error": "failed to send document requests"}), 500

    if updated > 0:
        add_history_entry(
            g.db,
            user_id,
            g.current_user_id,
            "Отправлены запросы документов",
            f"Количество: {updated}",
        )

    return jsonify(
        {
            "success": True,
            "document_requests": requests,
            "updated": updated,
        }
    ), 200


@lk_bp.get("/case-history/<int:user_id>")
def get_case_history_endpoint(user_id: int):
    """Get case history for a specific user."""
    try:
        # Get current user to check permissions
        current_user = get_user_by_id(g.db, g.current_user_id)
        if not current_user:
            return jsonify({"success": False, "error": "Пользователь не найден"}), 404
        
        if g.current_user_id != user_id and not _viewer_may_access_client_case_data(
            g.db, g.current_user_id, user_id
        ):
            return jsonify({"success": False, "error": "Недостаточно прав"}), 403
        
        history = get_case_history(g.db, user_id)
        
        return jsonify({
            "success": True,
            "history": history
        }), 200
        
    except Exception as e:
        print(f"Error fetching case history: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": "Не удалось загрузить историю"}), 500


@lk_bp.put("/case-data/<int:user_id>")
def update_case_data(user_id: int):
    """Update case management data for a specific user."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(current_user["role_key"] or "")
    permissions = get_role_permissions(role_key)

    if not _viewer_may_access_client_case_data(g.db, g.current_user_id, user_id):
        return jsonify({"success": False, "error": "access denied"}), 403

    # Verify target user exists
    target_user = get_user_by_id(g.db, user_id)
    if not target_user:
        return jsonify({"success": False, "error": "target user not found"}), 404
    
    # Get payload
    payload = request.get_json(silent=True) or {}
    
    visa_type = str(payload.get("visa_type", "user")).strip()  # This is actually a role_key (костыль)
    target_date = payload.get("target_date")
    country = str(payload.get("country") or "").strip()
    timeline = payload.get("timeline", [])
    document_requests = payload.get("document_requests", [])
    referral_id = payload.get("referral_id")
    manager_id = payload.get("manager_id")

    # Validate data types
    if not isinstance(timeline, list):
        return jsonify({"success": False, "error": "timeline must be a list"}), 400
    if not isinstance(document_requests, list):
        return jsonify({"success": False, "error": "document_requests must be a list"}), 400
    
    # Права на «визовый путь» нужны только при смене роли клиента (не при правке графика/даты и т.д.)
    old_role = normalize_role_key(target_user["role_key"] or "")
    visa_type = normalize_role_key(visa_type)
    role_unchanged = old_role == visa_type

    if not role_unchanged:
        if user_id == g.current_user_id:
            return jsonify({"success": False, "error": "cannot change own role"}), 403
        if not can_assign_visa_type(role_key, visa_type):
            return jsonify({
                "success": False,
                "error": f"access denied: cannot assign role '{visa_type}'"
            }), 403
    
    # Get old case data to track changes
    old_case_data = get_case_data_by_user_id(g.db, user_id)
    # Archive metadata is managed only by /case-data/<user_id>/archive upload endpoint.
    archive_file_path = old_case_data.get("archive_file_path") if old_case_data else None
    archive_file_name = old_case_data.get("archive_file_name") if old_case_data else None

    if payload.get("timeline_manual") is None:
        timeline_manual = bool(old_case_data.get("timeline_manual")) if old_case_data else False
    else:
        timeline_manual = bool(payload.get("timeline_manual"))
    if payload.get("document_requests_manual") is None:
        document_requests_manual = (
            bool(old_case_data.get("document_requests_manual")) if old_case_data else False
        )
    else:
        document_requests_manual = bool(payload.get("document_requests_manual"))

    if old_case_data:
        document_requests = merge_document_requests_preserve_sent(
            old_case_data.get("document_requests"),
            document_requests,
        )
    if any(
        case_data_flag_is_true(item.get("sent"))
        for item in document_requests
        if isinstance(item, dict)
    ):
        document_requests_manual = True

    team_kind = team_assignment_kind_for_target(old_role)
    if team_kind == "client_managers":
        manager_id = get_primary_manager_id_for_client(g.db, user_id)
        referral_id = None
    else:
        manager_id = None
        referral_id = None

    # Track target_date changes
    if old_case_data:
        old_target_date = old_case_data.get("target_date")
        if old_target_date != target_date:
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "Изменена дата записи в консульство",
                f"{old_target_date or 'не указана'} → {target_date or 'не указана'}"
            )

    # Track country changes
    if old_case_data:
        old_country = str(old_case_data.get("country") or "").strip()
        if old_country != country:
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "Изменена страна кейса",
                f"{old_country or 'не указана'} → {country or 'не указана'}"
            )

    # Track archive changes
    if old_case_data:
        old_archive_name = old_case_data.get("archive_file_name")
        old_archive_path = old_case_data.get("archive_file_path")
        if old_archive_name != archive_file_name or old_archive_path != archive_file_path:
            if archive_file_name and archive_file_path:
                details = archive_file_name
            else:
                details = "Архив удален"
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "Обновлен архив готового кейса",
                details
            )

    # График заявки и чек-лист запросов документов (раньше в case_history не попадали)
    if old_case_data:
        old_timeline = old_case_data.get("timeline") or []
        old_docs = old_case_data.get("document_requests") or []
        snap = lambda data: json.dumps(data, sort_keys=True, ensure_ascii=False, default=str)
        if snap(old_timeline) != snap(timeline):
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "График заявки изменён",
                _case_history_timeline_details(old_timeline, timeline),
            )
        if snap(old_docs) != snap(document_requests):
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "Запросы документов изменены",
                _case_history_document_requests_details(old_docs, document_requests),
            )

    # Update user's actual role (костыль - visa_type is actually role_key)
    if not role_unchanged:
        success = update_user_role(g.db, user_id, visa_type)
        if success:
            new_role_def = get_role_definition(visa_type)
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "Изменена роль пользователя",
                f"{old_role} → {visa_type} ({new_role_def['visa_label_ru']})"
            )
        else:
            return jsonify({"success": False, "error": "failed to update user role"}), 500
    
    # Track visa_type changes in case_data
    if old_case_data:
        old_visa_type = old_case_data.get("visa_type", "digital_nomad")
        if old_visa_type != visa_type:
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "Изменен визовый путь",
                f"{old_visa_type} → {visa_type}"
            )
    
    # Save case data
    success = upsert_case_data(
        g.db,
        user_id,
        visa_type,
        target_date,
        country,
        archive_file_path,
        archive_file_name,
        timeline,
        document_requests,
        referral_id,
        manager_id,
        timeline_manual=timeline_manual,
        document_requests_manual=document_requests_manual,
    )
    
    if not success:
        return jsonify({"success": False, "error": "failed to save case data"}), 500

    old_manager_id = old_case_data.get("manager_id") if old_case_data else None
    if should_sync_manager_clients(g.db, user_id, old_manager_id, manager_id):
        sync_manager_clients_from_case_manager_id(g.db, user_id, manager_id)
    
    # Add general creation history entry only if new case
    if not old_case_data:
        add_history_entry(
            g.db,
            user_id,
            g.current_user_id,
            "Кейс создан",
            f"Визовый путь: {visa_type}"
        )
        if country:
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "Указана страна кейса",
                country
            )
        if archive_file_name and archive_file_path:
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "Загружен архив готового кейса",
                archive_file_name
            )
    
    # Log the action
    add_security_log(
        g.db,
        g.current_user_id,
        "case_data_updated",
        f"Обновлены данные кейса для пользователя #{user_id}",
        details=f"Визовый путь: {visa_type}, Шагов в timeline: {len(timeline)}",
        ip_address=_request_ip(),
    )
    
    return jsonify({"success": True}), 200


@lk_bp.post("/case-data/<int:user_id>/archive")
def upload_case_archive(user_id: int):
    """Upload archive file for a specific case."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(current_user["role_key"] or "")
    permissions = get_role_permissions(role_key)
    if not _viewer_may_access_client_case_data(g.db, g.current_user_id, user_id):
        return jsonify({"success": False, "error": "access denied"}), 403

    target_user = get_user_by_id(g.db, user_id)
    if not target_user:
        return jsonify({"success": False, "error": "target user not found"}), 404

    archive_file = request.files.get("archive")
    if not archive_file or not archive_file.filename:
        return jsonify({"success": False, "error": "archive file is required"}), 400

    try:
        file_service = FileService()
        archive_path = file_service.save_document(archive_file, user_id, "case-archive")
        stored_name = archive_file.filename
        file_size_bytes = os.path.getsize(file_service.get_file_path(archive_path))

        current_case = get_case_data_by_user_id(g.db, user_id)
        visa_type = (
            (current_case or {}).get("visa_type")
            or normalize_role_key(target_user["role_key"] or "")
            or "user"
        )
        target_date = (current_case or {}).get("target_date")
        country = str((current_case or {}).get("country") or "").strip()
        timeline = (current_case or {}).get("timeline") or []
        document_requests = (current_case or {}).get("document_requests") or []
        referral_id = (current_case or {}).get("referral_id")
        manager_id = (current_case or {}).get("manager_id")
        timeline_manual = bool((current_case or {}).get("timeline_manual"))
        document_requests_manual = bool((current_case or {}).get("document_requests_manual"))

        success = upsert_case_data(
            g.db,
            user_id,
            visa_type,
            target_date,
            country,
            archive_path,
            stored_name,
            timeline,
            document_requests,
            referral_id,
            manager_id,
            timeline_manual=timeline_manual,
            document_requests_manual=document_requests_manual,
        )
        if not success:
            return jsonify({"success": False, "error": "failed to save archive metadata"}), 500

        previous_path = (current_case or {}).get("archive_file_path")
        previous_name = (current_case or {}).get("archive_file_name")
        if previous_path != archive_path or previous_name != stored_name:
            add_history_entry(
                g.db,
                user_id,
                g.current_user_id,
                "Обновлен архив готового кейса",
                stored_name,
            )

        return jsonify({
            "success": True,
            "archive_file_name": stored_name,
            "archive_file_id": _case_archive_file_id(user_id, archive_path),
            "archive_file_size": file_size_bytes,
            "archive_download_url": _case_archive_download_url(user_id, archive_path),
        }), 201
    except ValueError as error:
        return jsonify({"success": False, "error": str(error)}), 400
    except Exception as error:
        return jsonify({"success": False, "error": f"archive upload failed: {error}"}), 500


@lk_bp.get("/case-data/<int:user_id>/archive/download")
def download_case_archive(user_id: int):
    """Download case archive through a protected endpoint without exposing storage path."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404
    if not _viewer_may_access_client_case_data(g.db, g.current_user_id, user_id):
        return jsonify({"success": False, "error": "access denied"}), 403

    case_data = get_case_data_by_user_id(g.db, user_id)
    if not case_data:
        return jsonify({"success": False, "error": "case not found"}), 404

    archive_file_path = case_data.get("archive_file_path")
    if not archive_file_path:
        return jsonify({"success": False, "error": "archive not found"}), 404

    file_service = FileService()
    file_path = file_service.get_file_path(archive_file_path)
    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": "archive not found"}), 404

    download_name = (case_data.get("archive_file_name") or "").strip() or os.path.basename(file_path)
    return send_file(file_path, as_attachment=True, download_name=download_name)


def _can_manage_case_templates(role_key: str) -> bool:
    """Шаблоны кейсов: уровни ролей 1–4 (management, admin, moderator, manager)."""
    return is_portal_staff_role(role_key)


def _can_access_case_data_endpoint(user_id: int) -> bool:
    """Те же права, что у GET /case-data/<user_id> (без загрузки кейса)."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return False
    role_key = normalize_role_key(current_user["role_key"] or "")
    permissions = get_role_permissions(role_key)
    return bool(
        "full_access" in permissions
        or "view_all_users" in permissions
        or "view_lower_users" in permissions
        or "communicate_with_clients" in permissions
        or g.current_user_id == user_id
    )


def _resolve_template_owner_id_for_client(client_user_id: int, visa_type: str) -> int:
    """Чей шаблон подставлять: персональный менеджер кейса, иначе глобальный для роли user, иначе текущий пользователь."""
    return resolve_template_owner_id(
        g.db, client_user_id, visa_type, fallback_viewer_id=g.current_user_id
    )


@lk_bp.get("/case-templates")
def list_case_templates():
    """Шаблоны кейсов текущего менеджера по всем доступным визовым путям."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(current_user["role_key"] or "")
    if not _can_manage_case_templates(role_key):
        return jsonify({"success": False, "error": "access denied"}), 403

    assignable = get_assignable_case_template_visa_types(
        role_key, viewer_user_id=g.current_user_id
    )
    saved = {t["visa_type"]: t for t in list_templates_for_manager(g.db, g.current_user_id)}

    merged = []
    for vt in assignable:
        key = vt["value"]
        row = saved.get(key)
        merged.append(
            {
                "visa_type": key,
                "label_ru": vt.get("label_ru") or key,
                "label_en": vt.get("label_en") or key,
                "has_saved_template": row is not None,
                "title": (row or {}).get("title") or "",
                "updated_at": (row or {}).get("updated_at") or "",
            }
        )

    return jsonify({"success": True, "templates": merged}), 200


@lk_bp.get("/case-templates/<visa_type>")
def get_case_template(visa_type: str):
    """Один шаблон по визовому пути (редактор) или для клиента (?for_client_user_id=)."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(current_user["role_key"] or "")
    if not _can_manage_case_templates(role_key):
        return jsonify({"success": False, "error": "access denied"}), 403

    visa_type = str(visa_type or "").strip()
    for_client = request.args.get("for_client_user_id", type=int)

    if for_client is not None:
        if not _can_access_case_data_endpoint(for_client):
            return jsonify({"success": False, "error": "access denied"}), 403
        owner_id = _resolve_template_owner_id_for_client(for_client, visa_type)
        row = get_template_for_manager(g.db, owner_id, visa_type)
    else:
        if not can_manage_case_template_visa(
            role_key, visa_type, editor_user_id=g.current_user_id
        ):
            return jsonify({"success": False, "error": "access denied for this visa type"}), 403
        row = get_template_for_manager(g.db, g.current_user_id, visa_type)
    if row:
        return jsonify({"success": True, "template": row}), 200

    return jsonify(
        {
            "success": True,
            "template": {
                "visa_type": visa_type,
                "title": "",
                "public_description": "",
                "processing_fee_eur": None,
                "duration_months": None,
                "timeline": [],
                "document_items": [],
                "updated_at": "",
            },
        }
    ), 200


@lk_bp.put("/case-templates/<visa_type>")
def put_case_template(visa_type: str):
    """Сохранить шаблон таймлайна и чек-листа документов."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    role_key = normalize_role_key(current_user["role_key"] or "")
    if not _can_manage_case_templates(role_key):
        return jsonify({"success": False, "error": "access denied"}), 403

    visa_type = str(visa_type or "").strip()
    if not can_manage_case_template_visa(
        role_key, visa_type, editor_user_id=g.current_user_id
    ):
        return jsonify({"success": False, "error": "access denied for this visa type"}), 403

    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title") or "").strip()
    public_description = str(payload.get("public_description") or "").strip()
    processing_fee = payload.get("processing_fee_eur")
    duration_months = payload.get("duration_months")
    timeline = payload.get("timeline", [])
    document_items = payload.get("document_items", [])

    if not isinstance(timeline, list):
        return jsonify({"success": False, "error": "timeline must be a list"}), 400
    if not isinstance(document_items, list):
        return jsonify({"success": False, "error": "document_items must be a list"}), 400

    fee_val = None
    if processing_fee is not None and str(processing_fee).strip() != "":
        try:
            fee_val = float(processing_fee)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "invalid processing_fee_eur"}), 400

    dur_val = None
    if duration_months is not None and str(duration_months).strip() != "":
        try:
            dur_val = int(duration_months)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "invalid duration_months"}), 400

    upsert_template_for_manager(
        g.db,
        g.current_user_id,
        visa_type,
        title,
        public_description,
        fee_val,
        dur_val,
        timeline,
        document_items,
    )

    add_security_log(
        g.db,
        g.current_user_id,
        "case_template_updated",
        f"Обновлён шаблон кейса: {visa_type}",
        details=f"Этапов: {len(timeline)}, позиций документов: {len(document_items)}",
        ip_address=_request_ip(),
    )

    row = get_template_for_manager(g.db, g.current_user_id, visa_type)
    return jsonify({"success": True, "template": row}), 200
