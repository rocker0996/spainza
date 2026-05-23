"""Migration: Add status and rejection_comment to documents table."""
import sqlite3
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent.parent
sys.path.insert(0, str(backend_path))

from utils.db import get_db_connection


def migrate():
    """Add status and rejection_comment columns to documents table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(documents)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'status' not in columns:
            print("Adding 'status' column to documents table...")
            cursor.execute("""
                ALTER TABLE documents
                ADD COLUMN status TEXT DEFAULT 'pending'
            """)
            print("[OK] Added 'status' column")
        else:
            print("'status' column already exists")
        
        if 'rejection_comment' not in columns:
            print("Adding 'rejection_comment' column to documents table...")
            cursor.execute("""
                ALTER TABLE documents
                ADD COLUMN rejection_comment TEXT
            """)
            print("[OK] Added 'rejection_comment' column")
        else:
            print("'rejection_comment' column already exists")
        
        conn.commit()
        print("\n[SUCCESS] Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n[ERROR] Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
