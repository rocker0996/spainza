"""Add per-message delete and reply columns."""
import os
import sys

if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from models.message import Message
from utils.db import get_db_connection


def migrate():
    conn = get_db_connection()
    try:
        Message._ensure_message_columns(conn)
        conn.execute(
            """
            UPDATE messages
            SET deleted_content_text = message_text
            WHERE deleted_by IS NOT NULL
              AND (deleted_content_text IS NULL OR TRIM(deleted_content_text) = '')
              AND message_text IS NOT NULL
              AND TRIM(message_text) != ''
            """
        )
        conn.commit()
        print("message delete/reply columns OK")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
