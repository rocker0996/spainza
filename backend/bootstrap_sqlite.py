"""Create bootstrap admin/demo users in SQLite when env vars are set."""

from __future__ import annotations

import os

from models.user import create_user, get_user_by_email, update_user_role
from utils.db import get_db_connection
from utils.security import hash_password


def _env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def ensure_bootstrap_users() -> None:
    admin_email = _env("BOOTSTRAP_ADMIN_EMAIL", "SPAINZA_ADMIN_EMAIL").lower()
    admin_password = _env("BOOTSTRAP_ADMIN_PASSWORD", "SPAINZA_ADMIN_PASSWORD")
    admin_name = _env("BOOTSTRAP_ADMIN_NAME", "SPAINZA_ADMIN_NAME") or "Platform Admin"
    admin_role = _env("BOOTSTRAP_ADMIN_ROLE") or "management"

    if not admin_email or not admin_password:
        return

    connection = get_db_connection()
    try:
        existing = get_user_by_email(connection, admin_email)
        if existing:
            update_user_role(connection, int(existing["id"]), admin_role)
            return

        user_id, _display_id = create_user(connection, admin_email, hash_password(admin_password))
        update_user_role(connection, int(user_id), admin_role)
        connection.execute("UPDATE users SET name = ? WHERE id = ?", (admin_name, user_id))
        connection.commit()

        demo_email = _env("BOOTSTRAP_DEMO_EMAIL").lower()
        demo_password = _env("BOOTSTRAP_DEMO_PASSWORD")
        if demo_email and demo_password and not get_user_by_email(connection, demo_email):
            demo_name = _env("BOOTSTRAP_DEMO_NAME") or "Demo Client"
            demo_id, _ = create_user(connection, demo_email, hash_password(demo_password))
            connection.execute("UPDATE users SET name = ? WHERE id = ?", (demo_name, demo_id))
            connection.commit()
    finally:
        connection.close()
