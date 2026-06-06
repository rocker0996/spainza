"""Telegram notifications: outbox queue and account linking."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Optional


LINK_CODE_TTL_MINUTES = 10
LOGIN_SESSION_TTL_MINUTES = 10
OUTBOX_MAX_ATTEMPTS = 8


def create_notification_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS notification_outbox (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            next_retry_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            sent_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_notification_outbox_pending
        ON notification_outbox (status, next_retry_at)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS user_telegram_links (
            user_id INTEGER PRIMARY KEY,
            telegram_chat_id INTEGER NOT NULL UNIQUE,
            telegram_user_id INTEGER,
            telegram_username TEXT,
            linked_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            is_active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_link_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            code_hash TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            used_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telegram_link_codes_hash
        ON telegram_link_codes (code_hash)
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_login_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_token TEXT NOT NULL UNIQUE,
            start_code TEXT NOT NULL,
            code_hash TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            user_id INTEGER,
            expires_at TEXT NOT NULL,
            completed_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telegram_login_sessions_poll
        ON telegram_login_sessions (poll_token)
        """
    )
    connection.commit()


def _hash_link_code(code: str, secret_key: str) -> str:
    normalized = str(code or "").strip()
    return hashlib.sha256(f"{normalized}:{secret_key}".encode("utf-8")).hexdigest()


def _now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def create_telegram_link_code(
    connection: sqlite3.Connection,
    user_id: int,
    secret_key: str,
) -> tuple[str, str]:
    """Create a one-time 6-digit link code. Returns (code, expires_at)."""
    connection.execute(
        """
        UPDATE telegram_link_codes
        SET used_at = datetime('now', 'localtime')
        WHERE user_id = ? AND used_at IS NULL
        """,
        (user_id,),
    )
    code = f"{secrets.randbelow(1_000_000):06d}"
    expires_at = (
        datetime.now() + timedelta(minutes=LINK_CODE_TTL_MINUTES)
    ).strftime("%Y-%m-%d %H:%M:%S")
    connection.execute(
        """
        INSERT INTO telegram_link_codes (user_id, code_hash, expires_at)
        VALUES (?, ?, ?)
        """,
        (user_id, _hash_link_code(code, secret_key), expires_at),
    )
    connection.commit()
    return code, expires_at


def consume_telegram_link_code(
    connection: sqlite3.Connection,
    code: str,
    secret_key: str,
) -> Optional[int]:
    """Validate code and return user_id if valid."""
    code_hash = _hash_link_code(code, secret_key)
    row = connection.execute(
        """
        SELECT id, user_id, expires_at, used_at
        FROM telegram_link_codes
        WHERE code_hash = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (code_hash,),
    ).fetchone()
    if not row or row["used_at"]:
        return None
    expires_at = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expires_at:
        return None
    connection.execute(
        "UPDATE telegram_link_codes SET used_at = ? WHERE id = ?",
        (_now_local(), row["id"]),
    )
    connection.commit()
    return int(row["user_id"])


def create_telegram_login_session(
    connection: sqlite3.Connection,
    secret_key: str,
) -> tuple[str, str, str]:
    """Create bot-app login session. Returns (poll_token, start_code, expires_at)."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    start_code = f"login{code}"
    poll_token = secrets.token_urlsafe(24)
    expires_at = (
        datetime.now() + timedelta(minutes=LOGIN_SESSION_TTL_MINUTES)
    ).strftime("%Y-%m-%d %H:%M:%S")
    connection.execute(
        """
        INSERT INTO telegram_login_sessions (poll_token, start_code, code_hash, expires_at)
        VALUES (?, ?, ?, ?)
        """,
        (poll_token, start_code, _hash_link_code(start_code, secret_key), expires_at),
    )
    connection.commit()
    return poll_token, start_code, expires_at


def consume_telegram_login_session(
    connection: sqlite3.Connection,
    start_code: str,
    secret_key: str,
) -> Optional[sqlite3.Row]:
    """Validate login start code and return session row."""
    normalized = str(start_code or "").strip()
    if not normalized:
        return None
    code_hash = _hash_link_code(normalized, secret_key)
    row = connection.execute(
        """
        SELECT id, poll_token, status, expires_at
        FROM telegram_login_sessions
        WHERE code_hash = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (code_hash,),
    ).fetchone()
    if not row or row["status"] != "pending":
        return None
    expires_at = datetime.strptime(row["expires_at"], "%Y-%m-%d %H:%M:%S")
    if datetime.now() > expires_at:
        connection.execute(
            "UPDATE telegram_login_sessions SET status = 'expired' WHERE id = ?",
            (int(row["id"]),),
        )
        connection.commit()
        return None
    return row


def complete_telegram_login_session(
    connection: sqlite3.Connection,
    session_id: int,
    user_id: int,
) -> None:
    connection.execute(
        """
        UPDATE telegram_login_sessions
        SET status = 'completed', user_id = ?, completed_at = ?
        WHERE id = ? AND status = 'pending'
        """,
        (user_id, _now_local(), session_id),
    )
    connection.commit()


def get_telegram_login_session_by_poll_token(
    connection: sqlite3.Connection,
    poll_token: str,
) -> Optional[sqlite3.Row]:
    return connection.execute(
        """
        SELECT id, poll_token, status, user_id, expires_at, completed_at
        FROM telegram_login_sessions
        WHERE poll_token = ?
        LIMIT 1
        """,
        (str(poll_token or "").strip(),),
    ).fetchone()


def upsert_telegram_link(
    connection: sqlite3.Connection,
    user_id: int,
    telegram_chat_id: int,
    *,
    telegram_user_id: Optional[int] = None,
    telegram_username: Optional[str] = None,
) -> None:
    connection.execute(
        """
        UPDATE user_telegram_links
        SET is_active = 0
        WHERE telegram_chat_id = ? AND user_id != ?
        """,
        (telegram_chat_id, user_id),
    )
    connection.execute(
        """
        INSERT INTO user_telegram_links (
            user_id, telegram_chat_id, telegram_user_id, telegram_username, is_active
        )
        VALUES (?, ?, ?, ?, 1)
        ON CONFLICT(user_id) DO UPDATE SET
            telegram_chat_id = excluded.telegram_chat_id,
            telegram_user_id = excluded.telegram_user_id,
            telegram_username = excluded.telegram_username,
            linked_at = datetime('now', 'localtime'),
            is_active = 1
        """,
        (
            user_id,
            telegram_chat_id,
            telegram_user_id,
            (telegram_username or "").strip() or None,
        ),
    )
    connection.execute(
        "UPDATE users SET notify_telegram = 1 WHERE id = ?",
        (user_id,),
    )
    connection.commit()


def get_telegram_link_by_telegram_user_id(
    connection: sqlite3.Connection,
    telegram_user_id: int,
) -> Optional[sqlite3.Row]:
    return connection.execute(
        """
        SELECT user_id, telegram_chat_id, telegram_user_id, telegram_username, linked_at
        FROM user_telegram_links
        WHERE telegram_user_id = ? AND is_active = 1
        LIMIT 1
        """,
        (int(telegram_user_id),),
    ).fetchone()


def get_telegram_link_for_user(
    connection: sqlite3.Connection,
    user_id: int,
) -> Optional[sqlite3.Row]:
    return connection.execute(
        """
        SELECT user_id, telegram_chat_id, telegram_user_id, telegram_username, linked_at
        FROM user_telegram_links
        WHERE user_id = ? AND is_active = 1
        LIMIT 1
        """,
        (user_id,),
    ).fetchone()


def deactivate_telegram_link(connection: sqlite3.Connection, user_id: int) -> bool:
    cursor = connection.execute(
        """
        UPDATE user_telegram_links
        SET is_active = 0
        WHERE user_id = ? AND is_active = 1
        """,
        (user_id,),
    )
    connection.execute(
        "UPDATE users SET notify_telegram = 0 WHERE id = ?",
        (user_id,),
    )
    connection.commit()
    return cursor.rowcount > 0


def enqueue_notification(
    connection: sqlite3.Connection,
    user_id: int,
    event_type: str,
    payload: dict[str, Any],
) -> Optional[int]:
    import json

    cursor = connection.execute(
        """
        INSERT INTO notification_outbox (user_id, event_type, payload_json)
        VALUES (?, ?, ?)
        """,
        (user_id, event_type, json.dumps(payload, ensure_ascii=False)),
    )
    connection.commit()
    return cursor.lastrowid


def fetch_pending_notifications(
    connection: sqlite3.Connection,
    *,
    limit: int = 20,
) -> list[sqlite3.Row]:
    return connection.execute(
        """
        SELECT id, user_id, event_type, payload_json, attempts
        FROM notification_outbox
        WHERE status = 'pending'
          AND next_retry_at <= datetime('now', 'localtime')
        ORDER BY id ASC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def mark_notification_sent(connection: sqlite3.Connection, notification_id: int) -> None:
    connection.execute(
        """
        UPDATE notification_outbox
        SET status = 'sent', sent_at = datetime('now', 'localtime'), last_error = NULL
        WHERE id = ?
        """,
        (notification_id,),
    )
    connection.commit()


def mark_notification_failed(
    connection: sqlite3.Connection,
    notification_id: int,
    error_message: str,
    *,
    attempts: int,
) -> None:
    if attempts >= OUTBOX_MAX_ATTEMPTS:
        status = "failed"
        delay_seconds = 0
    else:
        status = "pending"
        delay_seconds = min(3600, 30 * (2 ** max(0, attempts - 1)))

    next_retry = (
        datetime.now() + timedelta(seconds=delay_seconds)
    ).strftime("%Y-%m-%d %H:%M:%S")
    connection.execute(
        """
        UPDATE notification_outbox
        SET status = ?, attempts = ?, last_error = ?, next_retry_at = ?
        WHERE id = ?
        """,
        (status, attempts, (error_message or "")[:500], next_retry, notification_id),
    )
    connection.commit()
