"""Привязка клиента к менеджеру: manager_clients + case_data.manager_id."""

from __future__ import annotations

import secrets
import sqlite3
from typing import Optional

from models.case_data import get_case_data_by_user_id, upsert_case_data
from models.user import (
    assign_client_to_manager,
    get_user_by_id,
    is_portal_staff_role,
    normalize_role_key,
)
from services.case_template_apply import materialize_case_from_template_if_needed


def resolve_manager_id_from_invite_token(
    connection: sqlite3.Connection, token: str
) -> Optional[int]:
    """Вернуть id менеджера по токену приглашения или None."""
    t = (token or "").strip()
    if not t:
        return None
    row = connection.execute(
        "SELECT id, role_key FROM users WHERE manager_invite_token = ?",
        (t,),
    ).fetchone()
    if not row:
        return None
    rk = normalize_role_key(row["role_key"] or "")
    if not is_portal_staff_role(rk):
        return None
    return int(row["id"])


def get_manager_invite_token(connection: sqlite3.Connection, user_id: int) -> Optional[str]:
    row = connection.execute(
        "SELECT manager_invite_token FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row or not row["manager_invite_token"]:
        return None
    return str(row["manager_invite_token"])


def ensure_manager_invite_token(connection: sqlite3.Connection, user_id: int) -> Optional[str]:
    """Создать или вернуть токен приглашения для персонала ЛК."""
    existing = get_manager_invite_token(connection, user_id)
    if existing:
        return existing
    user = get_user_by_id(connection, user_id)
    if not user:
        return None
    rk = normalize_role_key(user["role_key"] or "")
    if not is_portal_staff_role(rk):
        return None
    for _ in range(8):
        token = secrets.token_urlsafe(16)
        try:
            connection.execute(
                "UPDATE users SET manager_invite_token = ? WHERE id = ?",
                (token, user_id),
            )
            connection.commit()
            return token
        except sqlite3.IntegrityError:
            connection.rollback()
    return None


def _normalize_manager_id(value: object) -> int | None:
    if value is None:
        return None
    try:
        mid = int(value)
    except (TypeError, ValueError):
        return None
    return mid if mid > 0 else None


def sync_manager_clients_from_case_manager_id(
    connection: sqlite3.Connection, client_id: int, manager_id: int | None
) -> None:
    """Синхронизировать manager_clients с case_data.manager_id (один менеджер на клиента)."""
    mid = _normalize_manager_id(manager_id)
    try:
        if mid is not None:
            connection.execute(
                "DELETE FROM manager_clients WHERE client_id = ? AND manager_id != ?",
                (client_id, mid),
            )
            connection.execute(
                "INSERT OR IGNORE INTO manager_clients (manager_id, client_id) VALUES (?, ?)",
                (mid, client_id),
            )
        else:
            connection.execute(
                "DELETE FROM manager_clients WHERE client_id = ?",
                (client_id,),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise


def should_sync_manager_clients(
    connection: sqlite3.Connection,
    client_id: int,
    old_manager_id: object,
    new_manager_id: object,
) -> bool:
    """True, если нужно обновить manager_clients: смена менеджера или рассинхрон."""
    old_mid = _normalize_manager_id(old_manager_id)
    new_mid = _normalize_manager_id(new_manager_id)
    if old_mid != new_mid:
        return True
    if new_mid is None:
        return False
    row = connection.execute(
        "SELECT 1 FROM manager_clients WHERE manager_id = ? AND client_id = ?",
        (new_mid, client_id),
    ).fetchone()
    return not row


def try_assign_client_to_manager(
    connection: sqlite3.Connection, manager_id: int, client_id: int
) -> tuple[bool, str]:
    """
    Закрепить клиента за менеджером.
    Возвращает (True, 'ok') или (False, код): client_not_found, target_not_client,
    personal_manager_taken, invalid_ids, save_failed.
    """
    if manager_id == client_id:
        return False, "invalid_ids"

    client = get_user_by_id(connection, client_id)
    if not client:
        return False, "client_not_found"

    client_role = normalize_role_key(client["role_key"] or "")
    if is_portal_staff_role(client_role):
        return False, "target_not_client"

    materialize_case_from_template_if_needed(
        connection, client_id, fallback_viewer_id=manager_id
    )

    case = get_case_data_by_user_id(connection, client_id)
    mid = case.get("manager_id") if case else None
    if mid is not None and int(mid) != int(manager_id):
        return False, "personal_manager_taken"

    rows = connection.execute(
        "SELECT manager_id FROM manager_clients WHERE client_id = ?",
        (client_id,),
    ).fetchall()
    for r in rows:
        if int(r["manager_id"]) != int(manager_id):
            return False, "personal_manager_taken"

    assign_client_to_manager(connection, manager_id, client_id)

    visa_type = normalize_role_key(client["role_key"] or "user")
    if case:
        ok = upsert_case_data(
            connection,
            client_id,
            str(case.get("visa_type") or visa_type),
            case.get("target_date"),
            case.get("country") or "",
            case.get("archive_file_path"),
            case.get("archive_file_name"),
            list(case.get("timeline") or []),
            list(case.get("document_requests") or []),
            case.get("referral_id"),
            manager_id,
            bool(case.get("timeline_manual")),
            bool(case.get("document_requests_manual")),
        )
    else:
        ok = upsert_case_data(
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
            manager_id,
        )

    if not ok:
        return False, "save_failed"
    return True, "ok"
