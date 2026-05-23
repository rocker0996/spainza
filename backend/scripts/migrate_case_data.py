"""Migration script to add referral_id and manager_id columns to case_data table."""

import sqlite3
import sys
from pathlib import Path

# Add parent directory to path to import utils
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.db import get_database_path


def migrate_case_data_table():
    """Add referral_id and manager_id columns to case_data table if they don't exist."""
    db_path = get_database_path()
    print(f"Database path: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(case_data)")
        columns = [row[1] for row in cursor.fetchall()]
        
        print(f"Current columns in case_data: {columns}")
        
        # Add referral_id column if it doesn't exist
        if 'referral_id' not in columns:
            print("Adding referral_id column...")
            cursor.execute("""
                ALTER TABLE case_data
                ADD COLUMN referral_id INTEGER
                REFERENCES users(id) ON DELETE SET NULL
            """)
            print("[OK] Added referral_id column")
        else:
            print("[OK] referral_id column already exists")
        
        # Add manager_id column if it doesn't exist
        if 'manager_id' not in columns:
            print("Adding manager_id column...")
            cursor.execute("""
                ALTER TABLE case_data
                ADD COLUMN manager_id INTEGER
                REFERENCES users(id) ON DELETE SET NULL
            """)
            print("[OK] Added manager_id column")
        else:
            print("[OK] manager_id column already exists")
        
        conn.commit()
        print("\n[SUCCESS] Migration completed successfully!")
        
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("Starting case_data table migration...\n")
    migrate_case_data_table()
