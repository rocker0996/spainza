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


def case_data_flag_is_true(value) -> bool:
    """Interpret boolean flags stored in case JSON (bool, 0/1, strings)."""
    if value is True or value == 1:
        return True
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return False


def merge_document_requests_preserve_sent(
    previous: Optional[list[dict[str, Any]]],
    incoming: Optional[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Keep sent/fulfilled flags when a concurrent save sends stale document_requests."""
    if not incoming:
        return []
    if not previous:
        return [dict(item) for item in incoming if isinstance(item, dict)]

    prev_by_id: dict[int, dict[str, Any]] = {}
    for item in previous:
        if not isinstance(item, dict) or item.get("id") is None:
            continue
        try:
            prev_by_id[int(item["id"])] = item
        except (TypeError, ValueError):
            continue

    merged: list[dict[str, Any]] = []
    for item in incoming:
        if not isinstance(item, dict):
            continue
        out = dict(item)
        try:
            rid = int(out.get("id"))
        except (TypeError, ValueError):
            merged.append(out)
            continue
        prev = prev_by_id.get(rid)
        if prev and case_data_flag_is_true(prev.get("sent")) and not case_data_flag_is_true(
            out.get("sent")
        ):
            out["sent"] = True
        if prev and case_data_flag_is_true(prev.get("fulfilled")) and not case_data_flag_is_true(
            out.get("fulfilled")
        ):
            out["fulfilled"] = True
        merged.append(out)
    return merged


def mark_document_requests_sent(
    connection: sqlite3.Connection,
    user_id: int,
    request_ids: list[int],
) -> tuple[bool, list[dict[str, Any]], int]:
    """Atomically mark document requests as sent to the client."""
    if not request_ids:
        return False, [], 0

    case_data = get_case_data_by_user_id(connection, user_id)
    if not case_data:
        return False, [], 0

    requests = case_data.get("document_requests")
    if not isinstance(requests, list):
        return False, [], 0

    id_set = {int(rid) for rid in request_ids}
    updated = 0
    matched = 0
    for req in requests:
        if not isinstance(req, dict):
            continue
        try:
            rid = int(req.get("id"))
        except (TypeError, ValueError):
            continue
        if rid not in id_set:
            continue
        matched += 1
        if not case_data_flag_is_true(req.get("sent")):
            updated += 1
        req["sent"] = True
        req["checked"] = False

    if matched == 0:
        return False, requests, 0

    ok = upsert_case_data(
        connection,
        user_id,
        case_data.get("visa_type") or "digital_nomad",
        case_data.get("target_date"),
        case_data.get("country") or "",
        case_data.get("archive_file_path"),
        case_data.get("archive_file_name"),
        case_data.get("timeline") or [],
        requests,
        referral_id=case_data.get("referral_id"),
        manager_id=case_data.get("manager_id"),
        timeline_manual=bool(case_data.get("timeline_manual")),
        document_requests_manual=True,
    )
    return ok, requests, updated


def _parse_case_document_request_id(request_id_raw: str | None) -> int | None:
    """Parse ``req_3`` or ``3`` into a numeric case document-request id."""
    if request_id_raw is None:
        return None
    raw = str(request_id_raw).strip()
    if not raw:
        return None
    if raw.startswith("req_"):
        raw = raw[4:]
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def find_case_document_request(
    case_data: Optional[dict[str, Any]], request_id_raw: str | None
) -> Optional[dict[str, Any]]:
    """Return a document request row from case_data by id."""
    parsed_id = _parse_case_document_request_id(request_id_raw)
    if parsed_id is None or not case_data:
        return None
    requests = case_data.get("document_requests")
    if not isinstance(requests, list):
        return None
    for req in requests:
        if not isinstance(req, dict):
            continue
        try:
            if int(req.get("id")) == parsed_id:
                return req
        except (TypeError, ValueError):
            continue
    return None


def set_case_document_request_fulfilled(
    connection: sqlite3.Connection,
    user_id: int,
    request_id_raw: str | None,
    *,
    fulfilled: bool = True,
) -> bool:
    """Mark a sent document request as fulfilled (or reset on recall)."""
    parsed_id = _parse_case_document_request_id(request_id_raw)
    if parsed_id is None:
        return False

    case_data = get_case_data_by_user_id(connection, user_id)
    if not case_data:
        return False

    requests = case_data.get("document_requests")
    if not isinstance(requests, list):
        return False

    updated = False
    for req in requests:
        if not isinstance(req, dict):
            continue
        try:
            if int(req.get("id")) != parsed_id:
                continue
        except (TypeError, ValueError):
            continue
        req["fulfilled"] = bool(fulfilled)
        updated = True
        break

    if not updated:
        return False

    return upsert_case_data(
        connection,
        user_id,
        case_data.get("visa_type") or "digital_nomad",
        case_data.get("target_date"),
        case_data.get("country") or "",
        case_data.get("archive_file_path"),
        case_data.get("archive_file_name"),
        case_data.get("timeline") or [],
        requests,
        referral_id=case_data.get("referral_id"),
        manager_id=case_data.get("manager_id"),
        timeline_manual=bool(case_data.get("timeline_manual")),
        document_requests_manual=bool(case_data.get("document_requests_manual")),
    )


def count_sent_document_requests(case_data: Optional[dict[str, Any]]) -> int:
    """Count open manager document requests waiting for client upload (nav badge)."""
    if not case_data:
        return 0
    requests = case_data.get("document_requests")
    if not isinstance(requests, list):
        return 0
    return sum(
        1
        for req in requests
        if isinstance(req, dict)
        and case_data_flag_is_true(req.get("sent"))
        and not case_data_flag_is_true(req.get("fulfilled"))
    )


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
