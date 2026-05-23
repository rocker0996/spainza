"""Migration script to add file support to messages table."""
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_db_connection

def migrate():
    """Add file_path and file_name columns to messages table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(messages)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add file_path column if it doesn't exist
        if 'file_path' not in columns:
            print("Adding file_path column to messages table...")
            cursor.execute("""
                ALTER TABLE messages 
                ADD COLUMN file_path TEXT
            """)
            print("✓ Added file_path column")
        else:
            print("✓ file_path column already exists")
        
        # Add file_name column if it doesn't exist
        if 'file_name' not in columns:
            print("Adding file_name column to messages table...")
            cursor.execute("""
                ALTER TABLE messages 
                ADD COLUMN file_name TEXT
            """)
            print("✓ Added file_name column")
        else:
            print("✓ file_name column already exists")
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("🔄 Running file support migration")
    print("=" * 60)
    migrate()
