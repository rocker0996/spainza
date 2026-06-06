"""Telegram Login Widget verification and account resolution."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import sqlite3
from typing import Any, Optional

from models.notifications import get_telegram_link_by_telegram_user_id, upsert_telegram_link
from models.user import create_user, get_user_by_email, get_user_by_id, is_account_deletion_pending
from services.auth_service import to_storage_datetime, utc_now
from services.case_template_apply import materialize_case_from_template_if_needed
from services.manager_client_assign import (
    resolve_manager_id_from_invite_token,
    try_assign_client_to_manager,
)
from services.welcome_support_message import send_support_welcome_to_new_user
from utils.security import hash_password

TELEGRAM_AUTH_MAX_AGE_SECONDS = 86400
_WIDGET_FIELDS = ("id", "first_name", "last_name", "username", "photo_url", "auth_date")


def _normalize_widget_payload(payload: dict[str, Any]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key in _WIDGET_FIELDS:
        if key not in payload:
            continue
        value = payload.get(key)
        if value is None or value == "":
            continue
        normalized[key] = str(value)
    return normalized


def verify_telegram_widget_auth(payload: dict[str, Any], bot_token: str) -> tuple[bool, str]:
    """Validate Telegram Login Widget callback (https://core.telegram.org/widgets/login)."""
    if not bot_token:
        return False, "bot_not_configured"

    received_hash = str(payload.get("hash") or "").strip()
    if not received_hash:
        return False, "missing_hash"

    data = _normalize_widget_payload(payload)
    if "id" not in data or "auth_date" not in data:
        return False, "missing_fields"

    try:
        auth_ts = int(data["auth_date"])
    except (TypeError, ValueError):
        return False, "invalid_auth_date"

    if utc_now().timestamp() - auth_ts > TELEGRAM_AUTH_MAX_AGE_SECONDS:
        return False, "auth_expired"

    check_parts = [f"{key}={data[key]}" for key in sorted(data.keys())]
    check_string = "\n".join(check_parts)
    secret_key = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calculated = hmac.new(
        secret_key,
        check_string.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        return False, "invalid_hash"

    return True, "ok"


def _telegram_placeholder_email(telegram_user_id: int) -> str:
    return f"tg{int(telegram_user_id)}@telegram.users.spainza"


def _display_name_from_telegram(data: dict[str, str]) -> str:
    first = str(data.get("first_name") or "").strip()
    last = str(data.get("last_name") or "").strip()
    full = f"{first} {last}".strip()
    if full:
        return full
    username = str(data.get("username") or "").strip()
    if username:
        return f"@{username}"
    return "Telegram user"


def resolve_or_create_user_from_telegram(
    connection: sqlite3.Connection,
    payload: dict[str, Any],
    *,
    manager_invite_token: str = "",
) -> tuple[Optional[int], bool, str]:
    """
    Find user by Telegram id or create a new one.
    Returns (user_id, created, error_code).
    """
    data = _normalize_widget_payload(payload)
    try:
        telegram_user_id = int(data["id"])
    except (KeyError, TypeError, ValueError):
        return None, False, "missing_telegram_id"

    telegram_chat_id = telegram_user_id
    telegram_username = str(data.get("username") or "").strip() or None
    display_name = _display_name_from_telegram(data)

    existing_link = get_telegram_link_by_telegram_user_id(connection, telegram_user_id)
    if existing_link:
        user_id = int(existing_link["user_id"])
        user_row = get_user_by_id(connection, user_id)
        if user_row and is_account_deletion_pending(user_row):
            return None, False, "account_deleted"
        connection.execute(
            "UPDATE users SET name = COALESCE(NULLIF(name, ''), ?) WHERE id = ?",
            (display_name, user_id),
        )
        connection.commit()
        upsert_telegram_link(
            connection,
            user_id,
            telegram_chat_id,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
        )
        return user_id, False, "ok"

    placeholder_email = _telegram_placeholder_email(telegram_user_id)
    if get_user_by_email(connection, placeholder_email):
        row = connection.execute(
            "SELECT id FROM users WHERE email = ? LIMIT 1",
            (placeholder_email,),
        ).fetchone()
        user_id = int(row["id"]) if row else None
        if not user_id:
            return None, False, "user_lookup_failed"
        user_row = get_user_by_id(connection, user_id)
        if user_row and is_account_deletion_pending(user_row):
            return None, False, "account_deleted"
        upsert_telegram_link(
            connection,
            user_id,
            telegram_chat_id,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
        )
        return user_id, False, "ok"

    password_hash = hash_password(secrets.token_urlsafe(48))
    user_id, _display_id = create_user(connection, placeholder_email, password_hash)
    verified_at = to_storage_datetime(utc_now())
    connection.execute(
        """
        UPDATE users
        SET
            name = ?,
            email_verified_at = ?,
            notify_telegram = 1
        WHERE id = ?
        """,
        (display_name, verified_at, user_id),
    )
    connection.commit()

    upsert_telegram_link(
        connection,
        user_id,
        telegram_chat_id,
        telegram_user_id=telegram_user_id,
        telegram_username=telegram_username,
    )

    try:
        materialize_case_from_template_if_needed(
            connection, user_id, fallback_viewer_id=None
        )
    except Exception:
        pass

    invite = (manager_invite_token or "").strip()
    if invite:
        mgr_id = resolve_manager_id_from_invite_token(connection, invite)
        if mgr_id:
            try:
                try_assign_client_to_manager(connection, mgr_id, user_id)
            except Exception:
                pass

    try:
        send_support_welcome_to_new_user(connection, user_id)
    except Exception:
        pass

    return user_id, True, "ok"
