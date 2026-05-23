"""Add per-user history clear timestamps on conversations (soft clear for audit)."""
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
        Message._ensure_conversation_columns(conn)
        conn.commit()
        print("conversation history clear columns OK")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
