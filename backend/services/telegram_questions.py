"""Structured client questions sent from Telegram into portal messages."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Optional

from models.telegram_conversation import (
    clear_dialog_state,
    create_telegram_conversation_tables,
    get_dialog_state,
    save_dialog_state,
)
from utils.time import to_storage_datetime


@dataclass(frozen=True)
class QuestionResult:
    created: bool
    reason: str
    conversation_id: Optional[str] = None


QUESTION_CATEGORIES = {
    "documents": ("Документы", "Documents"),
    "case": ("Статус кейса", "Case status"),
    "payment": ("Оплата", "Payment"),
    "meeting": ("Встреча", "Meeting"),
    "technical": ("Техническая проблема", "Technical issue"),
    "other": ("Другое", "Other"),
}


def start_question(
    connection: sqlite3.Connection,
    *,
    user_id: int,
    chat_id: int,
    category: str,
    context: Optional[dict] = None,
) -> None:
    create_telegram_conversation_tables(connection)
    normalized = category if category in QUESTION_CATEGORIES else "other"
    save_dialog_state(
        connection,
        chat_id=chat_id,
        user_id=user_id,
        flow="question_text",
        category=normalized,
        context=context,
    )


def cancel_question(connection: sqlite3.Connection, chat_id: int) -> None:
    clear_dialog_state(connection, chat_id)


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone() is not None


def _recipient_id(connection: sqlite3.Connection, user_id: int, support_user_id: int) -> int:
    if _table_exists(connection, "manager_clients"):
        row = connection.execute(
            "SELECT manager_id FROM manager_clients WHERE client_id = ? ORDER BY assigned_at ASC, id ASC LIMIT 1",
            (user_id,),
        ).fetchone()
        if row:
            return int(row["manager_id"])
    return int(support_user_id)


def consume_question_text(
    connection: sqlite3.Connection,
    *,
    chat_id: int,
    update_id: int,
    text: str,
    locale: str,
    support_user_id: int,
) -> QuestionResult:
    create_telegram_conversation_tables(connection)
    state = get_dialog_state(connection, chat_id)
    if not state or state["flow"] != "question_text":
        return QuestionResult(False, "no_active_question")
    body = str(text or "").strip()
    if not body:
        return QuestionResult(False, "empty_text")

    inserted = connection.execute(
        "INSERT OR IGNORE INTO telegram_processed_updates (update_id, processed_at) VALUES (?, ?)",
        (int(update_id), to_storage_datetime()),
    )
    if inserted.rowcount == 0:
        connection.commit()
        return QuestionResult(False, "duplicate_update")

    user_id = int(state["user_id"])
    receiver_id = _recipient_id(connection, user_id, support_user_id)
    low, high = sorted((user_id, receiver_id))
    conversation_id = f"conv_{low}_{high}"
    now = to_storage_datetime()
    connection.execute(
        """
        INSERT INTO conversations (id, user1_id, user2_id, last_message_at, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET last_message_at=excluded.last_message_at,
            user1_deleted=0, user2_deleted=0
        """,
        (conversation_id, low, high, now, now),
    )
    category = QUESTION_CATEGORIES.get(state["category"], QUESTION_CATEGORIES["other"])
    category_label = category[1] if locale == "en" else category[0]
    context = state.get("context") or {}
    stage = str(context.get("active_stage") or "").strip()
    header = f"Telegram · {category_label}"
    if stage:
        header += f"\n{'Stage' if locale == 'en' else 'Этап'}: {stage}"
    message_text = f"[{header}]\n\n{body}"
    connection.execute(
        """
        INSERT INTO messages (conversation_id, sender_id, receiver_id, message_text, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (conversation_id, user_id, receiver_id, message_text, now),
    )
    connection.execute("DELETE FROM telegram_dialog_states WHERE chat_id = ?", (chat_id,))
    connection.commit()
    return QuestionResult(True, "created", conversation_id)
