"""Migration script to add delete columns to conversations table."""
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
    """Add user1_deleted, user2_deleted columns to conversations and is_system_message to messages."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Check if columns already exist
        cursor.execute("PRAGMA table_info(conversations)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # Add user1_deleted column if it doesn't exist
        if 'user1_deleted' not in columns:
            print("Adding user1_deleted column to conversations table...")
            cursor.execute("""
                ALTER TABLE conversations 
                ADD COLUMN user1_deleted INTEGER DEFAULT 0
            """)
            print("✓ Added user1_deleted column")
        else:
            print("✓ user1_deleted column already exists")
        
        # Add user2_deleted column if it doesn't exist
        if 'user2_deleted' not in columns:
            print("Adding user2_deleted column to conversations table...")
            cursor.execute("""
                ALTER TABLE conversations 
                ADD COLUMN user2_deleted INTEGER DEFAULT 0
            """)
            print("✓ Added user2_deleted column")
        else:
            print("✓ user2_deleted column already exists")
        
        # Check messages table
        cursor.execute("PRAGMA table_info(messages)")
        msg_columns = [row[1] for row in cursor.fetchall()]
        
        # Add is_system_message column if it doesn't exist
        if 'is_system_message' not in msg_columns:
            print("Adding is_system_message column to messages table...")
            cursor.execute("""
                ALTER TABLE messages 
                ADD COLUMN is_system_message INTEGER DEFAULT 0
            """)
            print("✓ Added is_system_message column")
        else:
            print("✓ is_system_message column already exists")
        
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
    print("🔄 Running messages delete migration")
    print("=" * 60)
    migrate()
