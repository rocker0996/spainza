"""Add file_path column to documents table."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.db import get_db_connection


def migrate():
    """Add file_path column to documents table."""
    conn = get_db_connection()
    try:
        # Check if column already exists
        cursor = conn.execute("PRAGMA table_info(documents)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'file_path' in columns:
            print("Column 'file_path' already exists in documents table")
            return
        
        # Add file_path column
        conn.execute("""
            ALTER TABLE documents 
            ADD COLUMN file_path TEXT
        """)
        conn.commit()
        print("Successfully added 'file_path' column to documents table")
        
    except Exception as e:
        print(f"Error during migration: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    print("Running migration: Add file_path to documents table...")
    migrate()
    print("Migration complete!")
