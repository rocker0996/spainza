"""Internal staff notes for client cases."""

import json
import sqlite3
from typing import Any

from utils.time import normalize_storage_datetime, to_storage_datetime


DEFAULT_CHECKLIST = [
    {"id": "sanctions_checked", "label": "Проверено на санкции", "checked": False},
    {"id": "originals_received", "label": "Оригиналы получены", "checked": False},
    {"id": "translation_ordered", "label": "Нотариальный перевод заказан", "checked": False},
    {"id": "client_warned_deadlines", "label": "Клиент предупрежден о сроках", "checked": False},
]


def create_case_notes_table(connection: sqlite3.Connection) -> None:
    """Create case_notes table if it does not exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS case_notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            general_notes TEXT,
            risk_notes TEXT,
            payment_notes TEXT,
            next_contact_at TEXT,
            priority TEXT NOT NULL DEFAULT 'normal',
            checklist TEXT,
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            updated_by INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (updated_by) REFERENCES users(id) ON DELETE SET NULL
        )
        """
    )
    connection.commit()


def _safe_json_list(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return [dict(item) for item in DEFAULT_CHECKLIST]
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return [dict(item) for item in DEFAULT_CHECKLIST]
    if not isinstance(parsed, list):
        return [dict(item) for item in DEFAULT_CHECKLIST]
    out: list[dict[str, Any]] = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "id": str(item.get("id") or "").strip(),
                "label": str(item.get("label") or "").strip(),
                "checked": bool(item.get("checked")),
            }
        )
    return out or [dict(item) for item in DEFAULT_CHECKLIST]


def _row_to_notes(row) -> dict[str, Any]:
    return {
        "user_id": row["user_id"],
        "general_notes": row["general_notes"] or "",
        "risk_notes": row["risk_notes"] or "",
        "payment_notes": row["payment_notes"] or "",
        "next_contact_at": normalize_storage_datetime(row["next_contact_at"]),
        "priority": row["priority"] or "normal",
        "checklist": _safe_json_list(row["checklist"]),
        "created_at": normalize_storage_datetime(row["created_at"]),
        "updated_at": normalize_storage_datetime(row["updated_at"]),
        "updated_by": row["updated_by"],
        "updated_by_name": row["updated_by_name"],
        "updated_by_email": row["updated_by_email"],
    }


def default_case_notes(user_id: int) -> dict[str, Any]:
    return {
        "user_id": int(user_id),
        "general_notes": "",
        "risk_notes": "",
        "payment_notes": "",
        "next_contact_at": None,
        "priority": "normal",
        "checklist": [dict(item) for item in DEFAULT_CHECKLIST],
        "created_at": None,
        "updated_at": None,
        "updated_by": None,
        "updated_by_name": None,
        "updated_by_email": None,
    }


def get_case_notes(connection: sqlite3.Connection, user_id: int) -> dict[str, Any]:
    create_case_notes_table(connection)
    row = connection.execute(
        """
        SELECT cn.*, u.name AS updated_by_name, u.email AS updated_by_email
        FROM case_notes cn
        LEFT JOIN users u ON u.id = cn.updated_by
        WHERE cn.user_id = ?
        """,
        (int(user_id),),
    ).fetchone()
    if not row:
        return default_case_notes(int(user_id))
    return _row_to_notes(row)


def upsert_case_notes(
    connection: sqlite3.Connection,
    user_id: int,
    editor_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    create_case_notes_table(connection)
    checklist = payload.get("checklist")
    if not isinstance(checklist, list):
        checklist = DEFAULT_CHECKLIST
    normalized_checklist = []
    for item in checklist:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        normalized_checklist.append(
            {
                "id": str(item.get("id") or label).strip(),
                "label": label[:160],
                "checked": bool(item.get("checked")),
            }
        )
    if not normalized_checklist:
        normalized_checklist = [dict(item) for item in DEFAULT_CHECKLIST]

    priority = str(payload.get("priority") or "normal").strip().lower()
    if priority not in {"low", "normal", "high", "urgent"}:
        priority = "normal"

    next_contact_at = payload.get("next_contact_at")
    if next_contact_at is not None:
        next_contact_at = str(next_contact_at).strip() or None

    now_text = to_storage_datetime()
    connection.execute(
        """
        INSERT INTO case_notes (
            user_id, general_notes, risk_notes, payment_notes, next_contact_at,
            priority, checklist, created_at, updated_at, updated_by
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            general_notes = excluded.general_notes,
            risk_notes = excluded.risk_notes,
            payment_notes = excluded.payment_notes,
            next_contact_at = excluded.next_contact_at,
            priority = excluded.priority,
            checklist = excluded.checklist,
            updated_at = excluded.updated_at,
            updated_by = excluded.updated_by
        """,
        (
            int(user_id),
            str(payload.get("general_notes") or "").strip(),
            str(payload.get("risk_notes") or "").strip(),
            str(payload.get("payment_notes") or "").strip(),
            next_contact_at,
            priority,
            json.dumps(normalized_checklist, ensure_ascii=False),
            now_text,
            now_text,
            int(editor_id),
        ),
    )
    connection.commit()
    return get_case_notes(connection, int(user_id))
