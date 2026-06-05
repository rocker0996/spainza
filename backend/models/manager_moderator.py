"""Связь менеджер ↔ модератор (множественная)."""

from __future__ import annotations

import sqlite3

from models.user import get_role_definition, get_user_by_id, is_portal_staff_role, normalize_role_key


def create_manager_moderators_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS manager_moderators (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (moderator_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(manager_id, moderator_id)
        )
        """
    )
    _migrate_manager_moderators_drop_slots(connection)
    connection.commit()


def _migrate_manager_moderators_drop_slots(connection: sqlite3.Connection) -> None:
    cols = {
        row[1] for row in connection.execute("PRAGMA table_info(manager_moderators)").fetchall()
    }
    if "slot" not in cols:
        return
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS manager_moderators_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_id INTEGER NOT NULL,
            moderator_id INTEGER NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (moderator_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(manager_id, moderator_id)
        )
        """
    )
    connection.execute(
        """
        INSERT OR IGNORE INTO manager_moderators_new (manager_id, moderator_id, assigned_at)
        SELECT manager_id, moderator_id, COALESCE(assigned_at, CURRENT_TIMESTAMP)
        FROM manager_moderators
        """
    )
    connection.execute("DROP TABLE manager_moderators")
    connection.execute("ALTER TABLE manager_moderators_new RENAME TO manager_moderators")


def is_manager_role_key(role_key: str) -> bool:
    return normalize_role_key(role_key or "") == "manager"


def is_moderator_role_key(role_key: str) -> bool:
    return normalize_role_key(role_key or "") == "moderator"


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


def get_moderator_user_rows_for_manager(
    connection: sqlite3.Connection, manager_id: int
) -> list[dict]:
    rows = connection.execute(
        """
        SELECT u.*
        FROM users u
        INNER JOIN manager_moderators mm ON u.id = mm.moderator_id
        WHERE mm.manager_id = ?
        ORDER BY mm.assigned_at ASC, mm.id ASC
        """,
        (manager_id,),
    ).fetchall()
    return [_user_team_payload(connection, r) for r in rows]


def add_manager_moderator_link(
    connection: sqlite3.Connection, manager_id: int, moderator_id: int
) -> tuple[bool, str]:
    manager = get_user_by_id(connection, manager_id)
    moderator = get_user_by_id(connection, moderator_id)
    if not manager or not moderator:
        return False, "user_not_found"
    if not is_manager_role_key(manager["role_key"] or ""):
        return False, "target_not_manager"
    if not is_moderator_role_key(moderator["role_key"] or ""):
        return False, "invalid_moderator_role"
    try:
        connection.execute(
            """
            INSERT OR IGNORE INTO manager_moderators (manager_id, moderator_id)
            VALUES (?, ?)
            """,
            (manager_id, moderator_id),
        )
        connection.commit()
        return True, "ok"
    except sqlite3.IntegrityError:
        connection.rollback()
        return False, "save_failed"


def remove_manager_moderator_link(
    connection: sqlite3.Connection, manager_id: int, moderator_id: int
) -> tuple[bool, str]:
    connection.execute(
        "DELETE FROM manager_moderators WHERE manager_id = ? AND moderator_id = ?",
        (manager_id, moderator_id),
    )
    connection.commit()
    return True, "ok"


def is_manager_assigned_to_moderator(
    connection: sqlite3.Connection, moderator_id: int, manager_id: int
) -> bool:
    row = connection.execute(
        """
        SELECT 1 FROM manager_moderators
        WHERE moderator_id = ? AND manager_id = ?
        """,
        (moderator_id, manager_id),
    ).fetchone()
    return bool(row)


def is_client_directly_assigned_to_staff(
    connection: sqlite3.Connection, staff_user_id: int, client_user_id: int
) -> bool:
    row = connection.execute(
        """
        SELECT 1 FROM manager_clients
        WHERE manager_id = ? AND client_id = ?
        LIMIT 1
        """,
        (staff_user_id, client_user_id),
    ).fetchone()
    return bool(row)


def is_client_of_moderator_managers(
    connection: sqlite3.Connection, moderator_id: int, client_user_id: int
) -> bool:
    row = connection.execute(
        """
        SELECT 1
        FROM manager_clients mc
        INNER JOIN manager_moderators mm ON mm.manager_id = mc.manager_id
        WHERE mm.moderator_id = ? AND mc.client_id = ?
        LIMIT 1
        """,
        (moderator_id, client_user_id),
    ).fetchone()
    return bool(row)


def moderator_may_access_user(
    connection: sqlite3.Connection, moderator_id: int, target_user_id: int
) -> bool:
    target = get_user_by_id(connection, target_user_id)
    if not target:
        return False
    target_role = normalize_role_key(target["role_key"] or "")
    if is_manager_role_key(target_role):
        return is_manager_assigned_to_moderator(connection, moderator_id, target_user_id)
    if is_portal_staff_role(target_role):
        return False
    if is_client_directly_assigned_to_staff(connection, moderator_id, target_user_id):
        return True
    return is_client_of_moderator_managers(connection, moderator_id, target_user_id)


def get_users_for_moderator(connection: sqlite3.Connection, moderator_id: int) -> list:
    cursor = connection.execute(
        """
        SELECT DISTINCT u.id, u.name, u.email, u.avatar, u.role_key, u.created_at, u.phone, u.display_id
        FROM users u
        WHERE u.id IN (
            SELECT mm.manager_id
            FROM manager_moderators mm
            WHERE mm.moderator_id = ?
            UNION
            SELECT mc.client_id
            FROM manager_clients mc
            INNER JOIN manager_moderators mm ON mm.manager_id = mc.manager_id
            WHERE mm.moderator_id = ?
            UNION
            SELECT mc.client_id
            FROM manager_clients mc
            WHERE mc.manager_id = ?
        )
        ORDER BY
            CASE WHEN u.role_key = 'manager' THEN 0 ELSE 1 END,
            u.created_at DESC
        """,
        (moderator_id, moderator_id, moderator_id),
    )
    return cursor.fetchall()


def viewer_uses_moderator_scoped_user_list(role_key: str, permissions: list[str] | set[str]) -> bool:
    perms = set(permissions)
    return normalize_role_key(role_key) == "moderator" or (
        "view_assignable_users" in perms
        and "view_lower_users" not in perms
        and "full_access" not in perms
        and "view_all_users" not in perms
    )
