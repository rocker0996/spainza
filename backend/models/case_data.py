"""Case management model for storing client case data."""

import json
import sqlite3
from typing import Any, Optional


def _ensure_case_data_columns(connection: sqlite3.Connection) -> None:
    """Ensure newly introduced columns exist in case_data table."""
    cursor = connection.execute("PRAGMA table_info(case_data)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    required_columns = {
        "country": "TEXT",
        "archive_file_path": "TEXT",
        "archive_file_name": "TEXT",
        "timeline_manual": "INTEGER DEFAULT 0",
        "document_requests_manual": "INTEGER DEFAULT 0",
    }

    for column_name, column_type in required_columns.items():
        if column_name not in existing_columns:
            connection.execute(f"ALTER TABLE case_data ADD COLUMN {column_name} {column_type}")


def create_case_data_table(connection: sqlite3.Connection) -> None:
    """Create case_data table if it doesn't exist."""
    connection.execute("""
        CREATE TABLE IF NOT EXISTS case_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL UNIQUE,
            visa_type TEXT DEFAULT 'digital_nomad',
            target_date TEXT,
            country TEXT,
            archive_file_path TEXT,
            archive_file_name TEXT,
            timeline_data TEXT,
            document_requests TEXT,
            referral_id INTEGER,
            manager_id INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (referral_id) REFERENCES users(id) ON DELETE SET NULL,
            FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE SET NULL
        )
    """)
    _ensure_case_data_columns(connection)
    connection.commit()


def get_case_data_by_user_id(connection: sqlite3.Connection, user_id: int) -> Optional[dict[str, Any]]:
    """Get case data for a specific user."""
    _ensure_case_data_columns(connection)
    cursor = connection.execute(
        """
        SELECT id, user_id, visa_type, target_date, country, archive_file_path,
               archive_file_name, timeline_data, document_requests, referral_id,
               manager_id, created_at, updated_at,
               timeline_manual, document_requests_manual
        FROM case_data
        WHERE user_id = ?
        """,
        (user_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None

    def _bool_col(idx: int) -> bool:
        try:
            return bool(row[idx])
        except (IndexError, TypeError):
            return False

    return {
        "id": row[0],
        "user_id": row[1],
        "visa_type": row[2],
        "target_date": row[3],
        "country": row[4] or "",
        "archive_file_path": row[5],
        "archive_file_name": row[6],
        "timeline": json.loads(row[7]) if row[7] else [],
        "document_requests": json.loads(row[8]) if row[8] else [],
        "referral_id": row[9],
        "manager_id": row[10],
        "created_at": row[11],
        "updated_at": row[12],
        "timeline_manual": _bool_col(13),
        "document_requests_manual": _bool_col(14),
    }


def count_sent_document_requests(case_data: Optional[dict[str, Any]]) -> int:
    """Count manager document requests marked as sent (nav badge)."""
    if not case_data:
        return 0
    requests = case_data.get("document_requests")
    if not isinstance(requests, list):
        return 0
    return sum(1 for req in requests if isinstance(req, dict) and req.get("sent", False))


def upsert_case_data(
    connection: sqlite3.Connection,
    user_id: int,
    visa_type: str,
    target_date: Optional[str],
    country: Optional[str],
    archive_file_path: Optional[str],
    archive_file_name: Optional[str],
    timeline: list[dict[str, Any]],
    document_requests: list[dict[str, Any]],
    referral_id: Optional[int] = None,
    manager_id: Optional[int] = None,
    timeline_manual: bool = False,
    document_requests_manual: bool = False,
) -> bool:
    """Insert or update case data for a user."""
    try:
        _ensure_case_data_columns(connection)
        print(f"[upsert_case_data] Starting for user_id={user_id}")
        print(f"[upsert_case_data] visa_type={visa_type}, target_date={target_date}")
        print(f"[upsert_case_data] country={country}, archive_file_name={archive_file_name}")
        print(f"[upsert_case_data] referral_id={referral_id}, manager_id={manager_id}")
        print(f"[upsert_case_data] timeline length={len(timeline)}, doc_requests length={len(document_requests)}")
        
        # Serialize lists to JSON
        timeline_json = json.dumps(timeline)
        document_requests_json = json.dumps(document_requests)
        
        # Check if record exists
        existing = get_case_data_by_user_id(connection, user_id)
        print(f"[upsert_case_data] Existing record: {existing is not None}")
        
        if existing:
            # Update existing record
            print(f"[upsert_case_data] Updating existing record")
            connection.execute(
                """
                UPDATE case_data
                SET visa_type = ?,
                    target_date = ?,
                    country = ?,
                    archive_file_path = ?,
                    archive_file_name = ?,
                    timeline_data = ?,
                    document_requests = ?,
                    referral_id = ?,
                    manager_id = ?,
                    timeline_manual = ?,
                    document_requests_manual = ?,
                    updated_at = datetime('now')
                WHERE user_id = ?
                """,
                (
                    visa_type,
                    target_date,
                    country,
                    archive_file_path,
                    archive_file_name,
                    timeline_json,
                    document_requests_json,
                    referral_id,
                    manager_id,
                    1 if timeline_manual else 0,
                    1 if document_requests_manual else 0,
                    user_id,
                )
            )
        else:
            # Insert new record
            print(f"[upsert_case_data] Inserting new record")
            connection.execute(
                """
                INSERT INTO case_data (user_id, visa_type, target_date, country,
                                      archive_file_path, archive_file_name,
                                      timeline_data, document_requests, referral_id, manager_id,
                                      timeline_manual, document_requests_manual)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    visa_type,
                    target_date,
                    country,
                    archive_file_path,
                    archive_file_name,
                    timeline_json,
                    document_requests_json,
                    referral_id,
                    manager_id,
                    1 if timeline_manual else 0,
                    1 if document_requests_manual else 0,
                )
            )
        
        connection.commit()
        print(f"[upsert_case_data] Success!")
        return True
    except Exception as e:
        import traceback
        print(f"[upsert_case_data] ERROR: {e}")
        print(f"[upsert_case_data] Traceback: {traceback.format_exc()}")
        connection.rollback()
        return False


def delete_case_data_by_user_id(connection: sqlite3.Connection, user_id: int) -> bool:
    """Delete case data for a specific user."""
    try:
        connection.execute("DELETE FROM case_data WHERE user_id = ?", (user_id,))
        connection.commit()
        return True
    except Exception:
        connection.rollback()
        return False
