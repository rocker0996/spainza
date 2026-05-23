"""Reset all messages and conversations to initial state - NO CONFIRMATION."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.db import get_db_connection

def reset_messages():
    """Delete all messages and conversations from database."""
    db = get_db_connection()
    
    try:
        # Delete all messages
        result = db.execute('DELETE FROM messages')
        messages_count = result.rowcount
        print(f"[OK] Deleted {messages_count} messages")
        
        # Delete all conversations
        result = db.execute('DELETE FROM conversations')
        conv_count = result.rowcount
        print(f"[OK] Deleted {conv_count} conversations")
        
        # Delete all uploaded files in storage/messages
        import shutil
        messages_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'storage', 'messages')
        deleted_folders = 0
        if os.path.exists(messages_dir):
            for item in os.listdir(messages_dir):
                item_path = os.path.join(messages_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    deleted_folders += 1
        print(f"[OK] Deleted {deleted_folders} user folders from storage")
        
        db.commit()
        print("\n[SUCCESS] Database cleaned successfully!")
        print("All chats and messages deleted, system returned to initial state.")
        
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Error during cleanup: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    print("=" * 60)
    print("RESET MESSAGES DATABASE")
    print("=" * 60)
    reset_messages()
