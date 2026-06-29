"""Per-manager case templates (timeline + document checklist) by visa path."""

import json
import sqlite3
from typing import Any, Optional

from utils.time import normalize_storage_datetime, to_storage_datetime


def create_manager_case_templates_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS manager_case_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_id INTEGER NOT NULL,
            visa_type TEXT NOT NULL,
            title TEXT NOT NULL DEFAULT '',
            public_description TEXT NOT NULL DEFAULT '',
            processing_fee_eur REAL,
            duration_months INTEGER,
            timeline_json TEXT NOT NULL DEFAULT '[]',
            document_items_json TEXT NOT NULL DEFAULT '[]',
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            UNIQUE(manager_id, visa_type),
            FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.commit()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "visa_type": row["visa_type"],
        "title": row["title"] or "",
        "public_description": row["public_description"] or "",
        "processing_fee_eur": row["processing_fee_eur"],
        "duration_months": row["duration_months"],
        "timeline": json.loads(row["timeline_json"] or "[]"),
        "document_items": json.loads(row["document_items_json"] or "[]"),
        "updated_at": normalize_storage_datetime(row["updated_at"]),
    }


def get_template_for_manager(
    connection: sqlite3.Connection, manager_id: int, visa_type: str
) -> Optional[dict[str, Any]]:
    cursor = connection.execute(
        """
        SELECT visa_type, title, public_description, processing_fee_eur, duration_months,
               timeline_json, document_items_json, updated_at
        FROM manager_case_templates
        WHERE manager_id = ? AND visa_type = ?
        """,
        (manager_id, visa_type),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_templates_for_manager(connection: sqlite3.Connection, manager_id: int) -> list[dict[str, Any]]:
    cursor = connection.execute(
        """
        SELECT visa_type, title, public_description, processing_fee_eur, duration_months,
               timeline_json, document_items_json, updated_at
        FROM manager_case_templates
        WHERE manager_id = ?
        ORDER BY visa_type
        """,
        (manager_id,),
    )
    return [_row_to_dict(row) for row in cursor.fetchall()]


def upsert_template_for_manager(
    connection: sqlite3.Connection,
    manager_id: int,
    visa_type: str,
    title: str,
    public_description: str,
    processing_fee_eur: Optional[float],
    duration_months: Optional[int],
    timeline: list[dict[str, Any]],
    document_items: list[dict[str, Any]],
) -> bool:
    timeline_json = json.dumps(timeline)
    document_json = json.dumps(document_items)
    cursor = connection.execute(
        """
        INSERT INTO manager_case_templates (
            manager_id, visa_type, title, public_description,
            processing_fee_eur, duration_months, timeline_json, document_items_json, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(manager_id, visa_type) DO UPDATE SET
            title = excluded.title,
            public_description = excluded.public_description,
            processing_fee_eur = excluded.processing_fee_eur,
            duration_months = excluded.duration_months,
            timeline_json = excluded.timeline_json,
            document_items_json = excluded.document_items_json,
            updated_at = excluded.updated_at
        """,
        (
            manager_id,
            visa_type,
            title,
            public_description,
            processing_fee_eur,
            duration_months,
            timeline_json,
            document_json,
            to_storage_datetime(),
        ),
    )
    connection.commit()
    return cursor.rowcount >= 0
