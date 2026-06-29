"""Security event logs for user accounts."""

import sqlite3

from utils.time import normalize_storage_datetime, to_storage_datetime


def create_security_logs_table(connection: sqlite3.Connection) -> None:
    """Create security logs table if it does not exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS security_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            event_title TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            ip_address TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
    )
    connection.commit()


def add_security_log(
    connection: sqlite3.Connection,
    user_id: int,
    event_type: str,
    event_title: str,
    details: str = "",
    ip_address: str = "",
) -> int:
    """Insert security event log and return id."""
    timestamp = to_storage_datetime()
    cursor = connection.execute(
        """
        INSERT INTO security_logs (
            user_id,
            event_type,
            event_title,
            details,
            ip_address,
            created_at
        ) VALUES (?, ?, ?, ?, ?, ?)
        """,
        (user_id, event_type, event_title, details, ip_address, timestamp),
    )
    connection.commit()
    return cursor.lastrowid


def get_security_logs_for_user(connection: sqlite3.Connection, user_id: int, limit: int = 30):
    """Get recent user security events."""
    cursor = connection.execute(
        """
        SELECT id, event_type, event_title, details, ip_address, created_at
        FROM security_logs
        WHERE user_id = ?
        ORDER BY datetime(created_at) DESC, id DESC
        LIMIT ?
        """,
        (user_id, max(1, min(limit, 100))),
    )
    rows = cursor.fetchall()
    return [
        {
            "id": row["id"],
            "event_type": row["event_type"],
            "event_title": row["event_title"],
            "details": row["details"],
            "ip_address": row["ip_address"],
            "created_at": normalize_storage_datetime(row["created_at"]),
        }
        for row in rows
    ]
