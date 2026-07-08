"""Client referral links, registration attribution, and dashboard stats."""

from __future__ import annotations

import secrets
import sqlite3
from typing import Any

from models.case_data import get_case_data_by_user_id, upsert_case_data
from models.user import get_role_definition, get_user_by_id, is_portal_staff_role, normalize_role_key
from services.manager_client_assign import try_assign_client_to_manager
from services.team_assignment import get_primary_manager_id_for_client

REFERRAL_REWARD_EUR = 100


def is_client_role_key(role_key: str) -> bool:
    return not is_portal_staff_role(normalize_role_key(role_key or ""))


def is_registered_referral_role(role_key: str) -> bool:
    return normalize_role_key(role_key or "") == "user"


def is_paid_client_referral_role(role_key: str) -> bool:
    key = normalize_role_key(role_key or "")
    return is_client_role_key(key) and key != "user"


def get_client_referral_token(connection: sqlite3.Connection, user_id: int) -> str | None:
    row = connection.execute(
        "SELECT client_referral_token FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if not row or not row["client_referral_token"]:
        return None
    return str(row["client_referral_token"])


def ensure_client_referral_token(connection: sqlite3.Connection, user_id: int) -> str | None:
    existing = get_client_referral_token(connection, user_id)
    if existing:
        return existing
    user = get_user_by_id(connection, user_id)
    if not user or not is_client_role_key(user["role_key"] or ""):
        return None
    for _ in range(8):
        token = secrets.token_urlsafe(16)
        try:
            connection.execute(
                "UPDATE users SET client_referral_token = ? WHERE id = ?",
                (token, user_id),
            )
            connection.commit()
            return token
        except sqlite3.IntegrityError:
            connection.rollback()
    return None


def resolve_referrer_id_from_token(connection: sqlite3.Connection, token: str) -> int | None:
    t = (token or "").strip()
    if not t:
        return None
    row = connection.execute(
        "SELECT id, role_key FROM users WHERE client_referral_token = ?",
        (t,),
    ).fetchone()
    if not row or not is_client_role_key(row["role_key"] or ""):
        return None
    return int(row["id"])


def set_case_referral_id(
    connection: sqlite3.Connection, client_id: int, referral_id: int | None
) -> bool:
    case = get_case_data_by_user_id(connection, client_id)
    client = get_user_by_id(connection, client_id)
    if not client:
        return False
    visa_type = normalize_role_key(client["role_key"] or "user")
    if case:
        return upsert_case_data(
            connection,
            client_id,
            str(case.get("visa_type") or visa_type),
            case.get("target_date"),
            case.get("country") or "",
            case.get("archive_file_path"),
            case.get("archive_file_name"),
            list(case.get("timeline") or []),
            list(case.get("document_requests") or []),
            referral_id,
            case.get("manager_id"),
            bool(case.get("timeline_manual")),
            bool(case.get("document_requests_manual")),
            completed_at=case.get("completed_at"),
            retention_cleanup_at=case.get("retention_cleanup_at"),
            referral_hold_eur=(
                100
                if referral_id and not case.get("referral_id") and not case.get("referral_hold_eur")
                else case.get("referral_hold_eur", 0)
            ),
            referral_paid_eur=case.get("referral_paid_eur", 0),
        )
    return upsert_case_data(
        connection,
        client_id,
        visa_type,
        None,
        "",
        None,
        None,
        [],
        [],
        referral_id,
        get_primary_manager_id_for_client(connection, client_id),
        referral_hold_eur=100 if referral_id else 0,
        referral_paid_eur=0,
    )


def apply_client_referral_invite(
    connection: sqlite3.Connection, token: str, new_user_id: int
) -> tuple[bool, str]:
    referrer_id = resolve_referrer_id_from_token(connection, token)
    if not referrer_id:
        return False, "referrer_not_found"
    if int(referrer_id) == int(new_user_id):
        return False, "self_referral"
    new_user = get_user_by_id(connection, new_user_id)
    if not new_user or not is_client_role_key(new_user["role_key"] or ""):
        return False, "target_not_client"

    if not set_case_referral_id(connection, new_user_id, referrer_id):
        return False, "save_failed"

    manager_id = get_primary_manager_id_for_client(connection, referrer_id)
    if manager_id:
        ok, code = try_assign_client_to_manager(connection, manager_id, new_user_id)
        if not ok:
            return True, f"referral_saved_manager_{code}"
    return True, "ok"


def referral_user_payload(connection: sqlite3.Connection, user_id: int | None) -> dict[str, Any] | None:
    if not user_id:
        return None
    user = get_user_by_id(connection, int(user_id))
    if not user:
        return None
    role_key = normalize_role_key(user["role_key"] or "")
    role = get_role_definition(role_key)
    return {
        "id": int(user["id"]),
        "display_id": (user["display_id"] or "").strip() or None,
        "name": user["name"] or "",
        "email": user["email"] or "",
        "avatar": user["avatar"] or "",
        "role": {"key": role["key"], "name_ru": role["name_ru"]},
    }


def get_referral_stats(connection: sqlite3.Connection, referrer_id: int) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT u.role_key, cd.referral_hold_eur, cd.referral_paid_eur
        FROM case_data cd
        INNER JOIN users u ON u.id = cd.user_id
        WHERE cd.referral_id = ?
        """,
        (referrer_id,),
    ).fetchall()
    registered = 0
    clients = 0
    hold_eur = 0
    paid_eur = 0
    for row in rows:
        role_key = row["role_key"] or ""
        if is_registered_referral_role(role_key):
            registered += 1
        elif is_paid_client_referral_role(role_key):
            clients += 1
        hold_eur += int(row["referral_hold_eur"] or 0)
        paid_eur += int(row["referral_paid_eur"] or 0)
    return {
        "registered_count": registered,
        "client_count": clients,
        "reward_eur": REFERRAL_REWARD_EUR,
        "hold_eur": hold_eur,
        "earned_eur": paid_eur,
    }


def list_referrals_for_referrer(connection: sqlite3.Connection, referrer_id: int) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            u.id, u.name, u.email, u.avatar, u.display_id, u.role_key, u.created_at,
            cd.referral_hold_eur, cd.referral_paid_eur
        FROM case_data cd
        INNER JOIN users u ON u.id = cd.user_id
        WHERE cd.referral_id = ?
        ORDER BY u.created_at DESC, u.id DESC
        """,
        (referrer_id,),
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        role_key = normalize_role_key(row["role_key"] or "")
        role = get_role_definition(role_key)
        items.append(
            {
                "id": int(row["id"]),
                "display_id": (row["display_id"] or "").strip() or None,
                "name": row["name"] or "",
                "email": row["email"] or "",
                "avatar": row["avatar"] or "",
                "created_at": row["created_at"] or "",
                "referral_hold_eur": int(row["referral_hold_eur"] or 0),
                "referral_paid_eur": int(row["referral_paid_eur"] or 0),
                "role": {"key": role["key"], "name_ru": role["name_ru"]},
            }
        )
    return items


def update_referral_amounts(
    connection: sqlite3.Connection,
    referred_user_id: int,
    *,
    hold_eur: int,
    paid_eur: int,
) -> bool:
    case = get_case_data_by_user_id(connection, referred_user_id)
    if not case or not case.get("referral_id"):
        return False
    client = get_user_by_id(connection, referred_user_id)
    if not client:
        return False
    return upsert_case_data(
        connection,
        referred_user_id,
        str(case.get("visa_type") or normalize_role_key(client["role_key"] or "user")),
        case.get("target_date"),
        case.get("country") or "",
        case.get("archive_file_path"),
        case.get("archive_file_name"),
        list(case.get("timeline") or []),
        list(case.get("document_requests") or []),
        case.get("referral_id"),
        case.get("manager_id"),
        bool(case.get("timeline_manual")),
        bool(case.get("document_requests_manual")),
        completed_at=case.get("completed_at"),
        retention_cleanup_at=case.get("retention_cleanup_at"),
        referral_hold_eur=hold_eur,
        referral_paid_eur=paid_eur,
    )


def get_staff_invite_stats(connection: sqlite3.Connection, staff_id: int) -> dict[str, int]:
    rows = connection.execute(
        """
        SELECT u.role_key
        FROM manager_clients mc
        INNER JOIN users u ON u.id = mc.client_id
        WHERE mc.manager_id = ?
        """,
        (staff_id,),
    ).fetchall()
    registered = 0
    clients = 0
    for row in rows:
        role_key = row["role_key"] or ""
        if is_registered_referral_role(role_key):
            registered += 1
        elif is_paid_client_referral_role(role_key):
            clients += 1
    return {
        "registered_count": registered,
        "client_count": clients,
        "reward_eur": REFERRAL_REWARD_EUR,
        "hold_eur": 0,
        "earned_eur": clients * REFERRAL_REWARD_EUR,
    }
