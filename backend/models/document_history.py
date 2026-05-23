"""Document history model for tracking changes to documents."""

import sqlite3
from typing import Optional, Any
from datetime import datetime


def create_document_history_table(connection: sqlite3.Connection) -> None:
    """Create the document_history table if it doesn't exist."""
    cursor = connection.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            editor_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            created_at TIMESTAMP DEFAULT (datetime('now', 'localtime')),
            FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (editor_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    connection.commit()


def add_document_history_entry(
    connection: sqlite3.Connection,
    document_id: int,
    user_id: int,
    editor_id: int,
    action: str,
    details: str = None
) -> bool:
    """Add a new history entry for a document."""
    try:
        cursor = connection.cursor()
        cursor.execute("""
            INSERT INTO document_history (document_id, user_id, editor_id, action, details)
            VALUES (?, ?, ?, ?, ?)
        """, (document_id, user_id, editor_id, action, details))
        connection.commit()
        return True
    except sqlite3.Error as e:
        print(f"Error adding document history entry: {e}")
        return False


def get_document_history_by_user(
    connection: sqlite3.Connection,
    user_id: int,
    limit: int = 50
) -> list[dict[str, Any]]:
    """Get history entries for all documents of a specific user."""
    cursor = connection.cursor()
    cursor.execute("""
        SELECT 
            dh.id,
            dh.document_id,
            dh.action,
            dh.details,
            dh.created_at,
            d.title as document_title,
            u.name as editor_name,
            u.email as editor_email,
            u.avatar as editor_avatar
        FROM document_history dh
        LEFT JOIN documents d ON dh.document_id = d.id
        LEFT JOIN users u ON dh.editor_id = u.id
        WHERE dh.user_id = ?
        ORDER BY dh.created_at DESC
        LIMIT ?
    """, (user_id, limit))
    
    rows = cursor.fetchall()
    history = []
    
    for row in rows:
        history.append({
            'id': row[0],
            'document_id': row[1],
            'action': row[2],
            'details': row[3],
            'created_at': row[4],
            'document_title': row[5],
            'editor': {
                'name': row[6],
                'email': row[7],
                'avatar': row[8]
            }
        })
    
    return history


def get_document_history_by_document(
    connection: sqlite3.Connection,
    document_id: int,
    limit: int = 50
) -> list[dict[str, Any]]:
    """Get history entries for a specific document."""
    cursor = connection.cursor()
    cursor.execute("""
        SELECT 
            dh.id,
            dh.action,
            dh.details,
            dh.created_at,
            u.name as editor_name,
            u.email as editor_email,
            u.avatar as editor_avatar
        FROM document_history dh
        LEFT JOIN users u ON dh.editor_id = u.id
        WHERE dh.document_id = ?
        ORDER BY dh.created_at DESC
        LIMIT ?
    """, (document_id, limit))
    
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
