"""Persistent Telegram dialog state and processed-update ledger."""

from __future__ import annotations

import json
import sqlite3
from datetime import timedelta
from typing import Any, Optional

from utils.time import parse_storage_datetime, to_storage_datetime, utc_now


QUESTION_TTL_MINUTES = 30


def create_telegram_conversation_tables(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_dialog_states (
            chat_id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            flow TEXT NOT NULL,
            category TEXT,
            context_json TEXT NOT NULL DEFAULT '{}',
            expires_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_processed_updates (
            update_id INTEGER PRIMARY KEY,
            processed_at TEXT NOT NULL
        )
        """
    )
    connection.commit()


def save_dialog_state(
    connection: sqlite3.Connection,
    *,
    chat_id: int,
    user_id: int,
    flow: str,
    category: Optional[str] = None,
    context: Optional[dict[str, Any]] = None,
) -> None:
    now = utc_now()
    connection.execute(
        """
        INSERT INTO telegram_dialog_states (
            chat_id, user_id, flow, category, context_json, expires_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(chat_id) DO UPDATE SET
            user_id=excluded.user_id, flow=excluded.flow, category=excluded.category,
            context_json=excluded.context_json, expires_at=excluded.expires_at,
            updated_at=excluded.updated_at
        """,
        (
            chat_id,
            user_id,
            flow,
            category,
            json.dumps(context or {}, ensure_ascii=False),
            to_storage_datetime(now + timedelta(minutes=QUESTION_TTL_MINUTES)),
            to_storage_datetime(now),
        ),
    )
    connection.commit()


def get_dialog_state(connection: sqlite3.Connection, chat_id: int) -> Optional[dict[str, Any]]:
    row = connection.execute(
        "SELECT chat_id, user_id, flow, category, context_json, expires_at FROM telegram_dialog_states WHERE chat_id = ?",
        (chat_id,),
    ).fetchone()
    if not row:
        return None
    expires_at = parse_storage_datetime(row["expires_at"])
    if not expires_at or utc_now() > expires_at:
        clear_dialog_state(connection, chat_id)
        return None
    try:
        context = json.loads(row["context_json"] or "{}")
    except (TypeError, json.JSONDecodeError):
        context = {}
    return {
        "chat_id": int(row["chat_id"]),
        "user_id": int(row["user_id"]),
        "flow": str(row["flow"]),
        "category": str(row["category"] or ""),
        "context": context if isinstance(context, dict) else {},
    }


def clear_dialog_state(connection: sqlite3.Connection, chat_id: int) -> None:
    connection.execute("DELETE FROM telegram_dialog_states WHERE chat_id = ?", (chat_id,))
    connection.commit()
