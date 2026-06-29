"""Retention cleanup for uploaded files."""

from __future__ import annotations

import sqlite3
from datetime import timedelta

from services.file_service import FileService
from utils.time import parse_storage_datetime, to_storage_datetime, utc_now


CHAT_FILE_TTL_DAYS = 90
COMPLETED_CASE_FILE_TTL_DAYS = 30


def _delete_relative_file(file_service: FileService, relative_path: str | None) -> None:
    if not relative_path:
        return
    file_service.delete_file(relative_path)


def cleanup_expired_files(
    connection: sqlite3.Connection,
    *,
    file_service: FileService | None = None,
) -> dict[str, int]:
    """Remove expired uploaded payloads while keeping audit/history records."""
    service = file_service or FileService()
    now = utc_now()
    chat_cutoff = to_storage_datetime(now - timedelta(days=CHAT_FILE_TTL_DAYS))
    case_cutoff = now - timedelta(days=COMPLETED_CASE_FILE_TTL_DAYS)
    counts = {
        "chat_messages": 0,
        "case_documents": 0,
        "case_archives": 0,
        "cases_cleaned": 0,
    }

    chat_rows = connection.execute(
        """
        SELECT id, image_path, file_path
        FROM messages
        WHERE created_at < ?
          AND (NULLIF(TRIM(COALESCE(image_path, '')), '') IS NOT NULL
               OR NULLIF(TRIM(COALESCE(file_path, '')), '') IS NOT NULL)
        """,
        (chat_cutoff,),
    ).fetchall()
    for row in chat_rows:
        _delete_relative_file(service, row["image_path"])
        _delete_relative_file(service, row["file_path"])
        connection.execute(
            """
            UPDATE messages
            SET image_path = NULL, file_path = NULL, file_name = NULL
            WHERE id = ?
            """,
            (row["id"],),
        )
        counts["chat_messages"] += 1

    case_rows = connection.execute(
        """
        SELECT id, user_id, completed_at, archive_file_path
        FROM case_data
        WHERE completed_at IS NOT NULL
          AND NULLIF(TRIM(COALESCE(completed_at, '')), '') IS NOT NULL
        """
    ).fetchall()
    for case in case_rows:
        completed_at = parse_storage_datetime(case["completed_at"])
        if not completed_at or completed_at > case_cutoff:
            continue

        document_rows = connection.execute(
            """
            SELECT id, file_path
            FROM documents
            WHERE user_id = ?
              AND NULLIF(TRIM(COALESCE(file_path, '')), '') IS NOT NULL
            """,
            (case["user_id"],),
        ).fetchall()
        for document in document_rows:
            _delete_relative_file(service, document["file_path"])
            connection.execute(
                """
                UPDATE documents
                SET file_path = NULL, file_size = '', last_action_at = ?
                WHERE id = ?
                """,
                (to_storage_datetime(now), document["id"]),
            )
            counts["case_documents"] += 1

        if case["archive_file_path"]:
            _delete_relative_file(service, case["archive_file_path"])
            counts["case_archives"] += 1

        connection.execute(
            """
            UPDATE case_data
            SET archive_file_path = NULL,
                archive_file_name = NULL,
                retention_cleanup_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (to_storage_datetime(now), to_storage_datetime(now), case["id"]),
        )
        counts["cases_cleaned"] += 1

    connection.commit()
    return counts
