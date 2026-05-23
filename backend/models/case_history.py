"""Case history model for tracking changes to case data."""

import sqlite3
from typing import Optional, Any
from datetime import datetime


def create_case_history_table(connection: sqlite3.Connection) -> None:
    """Create the case_history table if it doesn't exist."""
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS case_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            editor_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (editor_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.commit()


def add_history_entry(
    connection: sqlite3.Connection,
    user_id: int,
    editor_id: int,
    action: str,
    details: str = None
) -> bool:
    """Add a new history entry for a case."""
    try:
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO case_history (user_id, editor_id, action, details)
            VALUES (?, ?, ?, ?)
        """, (user_id, editor_id, action, details))
        connection.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error adding history entry: {e}")
        return False


def get_case_history(
    connection: sqlite3.Connection,
    user_id: int,
    limit: int = 50
) -> list[dict[str, Any]]:
    """Get history entries for a specific case."""
    cursor = connection.cursor()
    cursor.execute("""
        SELECT 
            ch.id,
            ch.action,
            ch.details,
            ch.created_at,
            u.name as editor_name,
            u.email as editor_email,
            u.avatar as editor_avatar
        FROM case_history ch
        LEFT JOIN users u ON ch.editor_id = u.id
        WHERE ch.user_id = ?
        ORDER BY ch.created_at DESC
        LIMIT ?
    """, (user_id, limit))
    
    rows = cursor.fetchall()
    history = []
    
    for row in rows:
        history.append({
            'id': row[0],
            'action': row[1],
            'details': row[2],
            'created_at': row[3],
            'editor': {
                'name': row[4],
                'email': row[5],
                'avatar': row[6]
            }
        })
    
    return history
