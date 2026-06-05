"""Закрепления в блоке «Работает над кейсом»: клиент↔менеджеры, менеджер↔модераторы."""

from __future__ import annotations

import sqlite3

from models.case_data import get_case_data_by_user_id, upsert_case_data
from models.manager_moderator import (
    add_manager_moderator_link,
    get_moderator_user_rows_for_manager,
    is_manager_role_key,
    is_moderator_role_key,
    remove_manager_moderator_link,
)
from models.user import (
    assign_client_to_manager,
    get_role_definition,
    get_user_by_id,
    is_client_assignable_staff_role,
    is_portal_staff_role,
    normalize_role_key,
)


def team_assignment_kind_for_target(target_role_key: str) -> str | None:
    rk = normalize_role_key(target_role_key or "")
    if is_manager_role_key(rk):
        return "manager_moderators"
    if is_moderator_role_key(rk):
        return "moderator_managers"
    if is_portal_staff_role(rk):
        return None
    return "client_managers"


def member_role_allowed_for_assignment_kind(kind: str | None, member_role_key: str) -> bool:
    """Единая проверка: подходит ли роль сотрудника для типа закрепления."""
    rk = normalize_role_key(member_role_key or "")
    if kind == "client_managers":
        return is_client_assignable_staff_role(rk)
    if kind == "manager_moderators":
        return is_moderator_role_key(rk)
    if kind == "moderator_managers":
        return is_manager_role_key(rk)
    return False


def expected_member_roles_for_assignment_kind(kind: str | None) -> list[str]:
    if kind == "client_managers":
        return ["management", "admin", "support", "moderator", "manager"]
    if kind == "manager_moderators":
        return ["moderator"]
    if kind == "moderator_managers":
        return ["manager"]
    return []


def _user_team_payload(connection: sqlite3.Connection, user_row) -> dict:
    role_key = normalize_role_key(user_row["role_key"] or "")
    role_data = get_role_definition(role_key)
    return {
        "id": int(user_row["id"]),
        "name": user_row["name"] or "",
        "email": user_row["email"] or "",
        "avatar": user_row["avatar"] or "",
        "display_id": (user_row["display_id"] or "").strip() or None,
        "role": {
            "key": role_data["key"],
            "name_ru": role_data["name_ru"],
        },
    }


def get_manager_ids_for_client(connection: sqlite3.Connection, client_id: int) -> list[int]:
    rows = connection.execute(
        """
        SELECT manager_id
        FROM manager_clients
        WHERE client_id = ?
        ORDER BY assigned_at ASC, id ASC
        """,
        (client_id,),
    ).fetchall()
    return [int(r["manager_id"]) for r in rows]


def get_primary_manager_id_for_client(connection: sqlite3.Connection, client_id: int) -> int | None:
    ids = get_manager_ids_for_client(connection, client_id)
    return ids[0] if ids else None


def sync_case_primary_manager(connection: sqlite3.Connection, client_id: int) -> None:
    """Первый закреплённый менеджер → case_data.manager_id (для «Ваш персональный менеджер»)."""
    primary_id = get_primary_manager_id_for_client(connection, client_id)
    case = get_case_data_by_user_id(connection, client_id)
    client = get_user_by_id(connection, client_id)
    if not client:
        return
    visa_type = normalize_role_key(client["role_key"] or "user")
    if case:
        upsert_case_data(
            connection,
            client_id,
            str(case.get("visa_type") or visa_type),
            case.get("target_date"),
            case.get("country") or "",
            case.get("archive_file_path"),
            case.get("archive_file_name"),
            list(case.get("timeline") or []),
            list(case.get("document_requests") or []),
            None,
            primary_id,
            bool(case.get("timeline_manual")),
            bool(case.get("document_requests_manual")),
        )
    elif primary_id is not None:
        upsert_case_data(
            connection,
            client_id,
            visa_type,
            None,
            "",
            None,
            None,
            [],
            [],
            None,
            primary_id,
        )


def get_team_members_for_user(connection: sqlite3.Connection, target_user_id: int) -> list[dict]:
    target = get_user_by_id(connection, target_user_id)
    if not target:
        return []
    kind = team_assignment_kind_for_target(target["role_key"] or "")
    if kind == "client_managers":
        rows = connection.execute(
            """
            SELECT u.*
            FROM users u
            INNER JOIN manager_clients mc ON u.id = mc.manager_id
            WHERE mc.client_id = ?
            ORDER BY mc.assigned_at ASC, mc.id ASC
            """,
            (target_user_id,),
        ).fetchall()
        return [_user_team_payload(connection, r) for r in rows]
    if kind == "manager_moderators":
        return get_moderator_user_rows_for_manager(connection, target_user_id)
    if kind == "moderator_managers":
        rows = connection.execute(
            """
            SELECT u.*
            FROM users u
            INNER JOIN manager_moderators mm ON u.id = mm.manager_id
            WHERE mm.moderator_id = ?
            ORDER BY mm.assigned_at ASC, mm.id ASC
            """,
            (target_user_id,),
        ).fetchall()
        return [_user_team_payload(connection, r) for r in rows]
    return []


def add_team_member(
    connection: sqlite3.Connection, target_user_id: int, member_user_id: int
) -> tuple[bool, str]:
    target = get_user_by_id(connection, target_user_id)
    member = get_user_by_id(connection, member_user_id)
    if not target or not member:
        return False, "user_not_found"

    kind = team_assignment_kind_for_target(target["role_key"] or "")
    member_role = normalize_role_key(member["role_key"] or "")

    if kind == "client_managers":
        if not member_role_allowed_for_assignment_kind(kind, member_role):
            return False, "invalid_member_role"
        if member_user_id == target_user_id:
            return False, "invalid_ids"
        if not assign_client_to_manager(connection, member_user_id, target_user_id):
            row = connection.execute(
                "SELECT 1 FROM manager_clients WHERE manager_id = ? AND client_id = ?",
                (member_user_id, target_user_id),
            ).fetchone()
            if row:
                return True, "already_linked"
            return False, "save_failed"
        sync_case_primary_manager(connection, target_user_id)
        return True, "ok"

    if kind == "manager_moderators":
        if not member_role_allowed_for_assignment_kind(kind, member_role):
            return False, "invalid_member_role"
        return add_manager_moderator_link(connection, target_user_id, member_user_id)

    if kind == "moderator_managers":
        if not member_role_allowed_for_assignment_kind(kind, member_role):
            return False, "invalid_member_role"
        return add_manager_moderator_link(connection, member_user_id, target_user_id)

    return False, "unsupported_target"


def remove_team_member(
    connection: sqlite3.Connection, target_user_id: int, member_user_id: int
) -> tuple[bool, str]:
    target = get_user_by_id(connection, target_user_id)
    if not target:
        return False, "user_not_found"

    kind = team_assignment_kind_for_target(target["role_key"] or "")

    if kind == "client_managers":
        connection.execute(
            "DELETE FROM manager_clients WHERE client_id = ? AND manager_id = ?",
            (target_user_id, member_user_id),
        )
        connection.commit()
        sync_case_primary_manager(connection, target_user_id)
        return True, "ok"

    if kind == "manager_moderators":
        return remove_manager_moderator_link(connection, target_user_id, member_user_id)

    if kind == "moderator_managers":
        return remove_manager_moderator_link(connection, member_user_id, target_user_id)

    return False, "unsupported_target"
