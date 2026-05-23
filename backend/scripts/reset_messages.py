"""Reset all messages and conversations to initial state."""
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
        db.execute('DELETE FROM messages')
        print("[OK] Udaleny vse soobshcheniya")
        
        # Delete all conversations
        db.execute('DELETE FROM conversations')
        print("[OK] Udaleny vse chaty")
        
        # Delete all uploaded files in storage/messages
        import shutil
        messages_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'storage', 'messages')
        if os.path.exists(messages_dir):
            for item in os.listdir(messages_dir):
                item_path = os.path.join(messages_dir, item)
                if os.path.isdir(item_path):
                    shutil.rmtree(item_path)
                    print(f"[OK] Udalena papka: {item}")
        
        db.commit()
        print("\n[SUCCESS] Baza dannykh soobshcheniy uspeshno ochishchena!")
        print("Vse chaty i soobshcheniya udaleny, sistema vernulas k nachalnomu sostoyaniyu.")
        
    except Exception as e:
        db.rollback()
        print(f"\n[ERROR] Oshibka pri ochistke: {e}")
        raise
    finally:
        db.close()

if __name__ == '__main__':
    print("=" * 60)
    print("Ochistka bazy dannykh soobshcheniy")
    print("=" * 60)
    print("\nVNIMANIE: Eto deystvie udalit VSE soobshcheniya i chaty!")
    
    confirm = input("\nProdolzhit? (yes/no): ")
    if confirm.lower() in ['yes', 'y']:
        reset_messages()
    else:
        print("\n[CANCEL] Operatsiya otmenena")
