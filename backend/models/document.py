"""Document model queries for SQLite."""

from datetime import datetime, timedelta
import sqlite3


def create_documents_table(connection: sqlite3.Connection) -> None:
    """Create documents table if it does not exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'uploaded',
            icon TEXT NOT NULL DEFAULT 'description',
            file_type TEXT NOT NULL DEFAULT 'PDF',
            file_size TEXT NOT NULL DEFAULT '1.0 MB',
            is_priority INTEGER NOT NULL DEFAULT 0,
            last_action_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
        """
    )
    connection.commit()


def get_documents_for_user(connection: sqlite3.Connection, user_id: int):
    """Return all user documents sorted by latest action."""
    cursor = connection.execute(
        """
        SELECT id, title, status, icon, file_type, file_size, is_priority, last_action_at, file_path, rejection_comment
        FROM documents
        WHERE user_id = ?
        ORDER BY datetime(last_action_at) DESC, id DESC
        """,
        (user_id,),
    )
    return cursor.fetchall()


def create_document(connection: sqlite3.Connection, user_id: int, title: str, file_path: str,
                   file_type: str, file_size: str, is_priority: int = 0) -> int:
    """Create a new document record."""
    cursor = connection.execute(
        """
        INSERT INTO documents (user_id, title, status, file_type, file_size, is_priority, file_path)
        VALUES (?, ?, 'pending', ?, ?, ?, ?)
        """,
        (user_id, title, file_type, file_size, is_priority, file_path),
    )
    connection.commit()
    return cursor.lastrowid


def get_document_by_id(connection: sqlite3.Connection, document_id: int):
    """Get a single document by ID."""
    cursor = connection.execute(
        """
        SELECT id, user_id, title, status, icon, file_type, file_size, is_priority, last_action_at, file_path, rejection_comment
        FROM documents
        WHERE id = ?
        """,
        (document_id,),
    )
    return cursor.fetchone()


def approve_document(connection: sqlite3.Connection, document_id: int) -> bool:
    """Approve a document by setting its status to 'approved'."""
    cursor = connection.execute(
        """
        UPDATE documents
        SET status = 'approved', rejection_comment = NULL, last_action_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (document_id,),
    )
    connection.commit()
    return cursor.rowcount > 0


def reject_document(connection: sqlite3.Connection, document_id: int, comment: str) -> bool:
    """Reject a document with a comment."""
    cursor = connection.execute(
        """
        UPDATE documents
        SET status = 'rejected', rejection_comment = ?, last_action_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (comment, document_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def revoke_approval(connection: sqlite3.Connection, document_id: int) -> bool:
    """Revoke approval and return document to pending status."""
    cursor = connection.execute(
        """
        UPDATE documents
        SET status = 'pending', rejection_comment = NULL, last_action_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (document_id,),
    )
    connection.commit()
    return cursor.rowcount > 0


def delete_document(connection: sqlite3.Connection, document_id: int) -> bool:
    """Delete a document by ID."""
    cursor = connection.execute(
        """
        DELETE FROM documents
        WHERE id = ?
        """,
        (document_id,),
    )
    connection.commit()
    return cursor.rowcount > 0


def replace_document_file(
    connection: sqlite3.Connection,
    document_id: int,
    file_path: str,
    file_type: str,
    file_size: str,
    title: str | None = None,
) -> bool:
    """Replace document file and return it to pending review."""
    if title is not None and str(title).strip():
        cursor = connection.execute(
            """
            UPDATE documents
            SET title = ?, file_path = ?, file_type = ?, file_size = ?, status = 'pending',
                rejection_comment = NULL, last_action_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (title, file_path, file_type, file_size, document_id),
        )
    else:
        cursor = connection.execute(
            """
            UPDATE documents
            SET file_path = ?, file_type = ?, file_size = ?, status = 'pending',
                rejection_comment = NULL, last_action_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (file_path, file_type, file_size, document_id),
        )
    connection.commit()
    return cursor.rowcount > 0


def count_rejected_documents_for_user(connection: sqlite3.Connection, user_id: int) -> int:
    """Count uploaded documents in rejected status for nav badge."""
    cursor = connection.execute(
        """
        SELECT COUNT(*) AS rejected_count
        FROM documents
        WHERE user_id = ? AND status = 'rejected'
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    return int(row["rejected_count"] or 0) if row else 0


def get_pending_document_counts_for_users(connection: sqlite3.Connection, user_ids: list[int]) -> dict[int, int]:
    """Return pending uploaded document counts for provided users."""
    if not user_ids:
        return {}

    placeholders = ",".join(["?"] * len(user_ids))
    cursor = connection.execute(
        f"""
        SELECT user_id, COUNT(*) AS pending_count
        FROM documents
        WHERE status = 'pending' AND user_id IN ({placeholders})
        GROUP BY user_id
        """,
        tuple(user_ids),
    )
    rows = cursor.fetchall()
    return {int(row["user_id"]): int(row["pending_count"] or 0) for row in rows}


def seed_documents_for_user(connection: sqlite3.Connection, user_id: int) -> None:
    """Seed initial document catalog for a new user profile."""
    cursor = connection.execute(
        "SELECT 1 FROM documents WHERE user_id = ? LIMIT 1",
        (user_id,),
    )
    if cursor.fetchone():
        return

    title_templates = [
        ("Скан паспорта", "badge", "pending", 1),
        ("Справка о доходах", "receipt_long", "pending", 0),
        ("Подтверждение адреса", "home_work", "pending", 0),
        ("Справка о несудимости", "gavel", "pending", 1),
        ("Медицинская страховка", "clinical_notes", "pending", 0),
        ("Диплом о высшем образовании", "school", "pending", 0),
        ("Свидетельство о браке", "diversity_3", "pending", 0),
        ("Трудовой контракт", "work", "pending", 0),
    ]

    rows = []
    now = datetime.utcnow()
    for index in range(42):
        title, icon, status, priority = title_templates[index % len(title_templates)]
        timestamp = now - timedelta(hours=index * 6)
        file_type = "PDF" if index % 2 == 0 else "JPG"
        file_size = f"{(index % 5) + 1}.{index % 9} MB"
        rows.append(
            (
                user_id,
                f"{title} #{index + 1}",
                status,
                icon,
                file_type,
                file_size,
                priority,
                timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            )
        )

    connection.executemany(
        """
        INSERT INTO documents (
            user_id,
            title,
            status,
            icon,
            file_type,
            file_size,
            is_priority,
            last_action_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    connection.commit()

