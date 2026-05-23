"""Clear all seeded test documents from the database."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.db import get_db_connection


def clear_seeded_documents():
    """Remove all documents from the documents table."""
    conn = get_db_connection()
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM documents")
        count_before = cursor.fetchone()[0]
        print(f"Dokumentov v baze do ochistki: {count_before}")
        
        if count_before > 0:
            conn.execute("DELETE FROM documents")
            conn.commit()
            print(f"Udaleno {count_before} testovykh dokumentov")
        else:
            print("Baza dannykh uzhe pusta")
            
    except Exception as e:
        print(f"Oshibka pri ochistke: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    print("Ochistka testovykh dokumentov iz bazy dannykh...")
    clear_seeded_documents()
    print("Gotovo!")
