"""Script to set specific user ID for dmitriy0996@gmail.com"""

import sys
from pathlib import Path

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.db import get_db_connection

def set_user_id_to_one(email: str):
    """Set user ID to 1 for specified email."""
    db = get_db_connection()
    
    try:
        # Check if user exists
        cursor = db.execute("SELECT id, email FROM users WHERE email = ?", (email,))
        user = cursor.fetchone()
        
        if not user:
            print(f"[ERROR] User with email {email} not found")
            return False
        
        current_id = user["id"]
        print(f"[INFO] Current ID for {email}: {current_id}")
        
        if current_id == 1:
            print(f"[OK] User already has ID = 1")
            return True
        
        # Check if ID 1 is already taken
        cursor = db.execute("SELECT id, email FROM users WHERE id = 1")
        existing_user = cursor.fetchone()
        
        if existing_user:
            print(f"[WARNING] ID = 1 is taken by: {existing_user['email']}")
            print(f"[INFO] Swapping IDs...")
            
            # Swap IDs using temporary ID
            temp_id = 999999
            
            # Move user with ID=1 to temp
            db.execute("UPDATE users SET id = ? WHERE id = 1", (temp_id,))
            
            # Move target user to ID=1
            db.execute("UPDATE users SET id = 1 WHERE email = ?", (email,))
            
            # Move temp user to old ID of target user
            db.execute("UPDATE users SET id = ? WHERE id = ?", (current_id, temp_id))
            
            db.commit()
            print(f"[SUCCESS] IDs swapped successfully:")
            print(f"   - {email} now has ID = 1")
            print(f"   - {existing_user['email']} now has ID = {current_id}")
        else:
            # ID 1 is free, just update
            db.execute("UPDATE users SET id = 1 WHERE email = ?", (email,))
            db.commit()
            print(f"[SUCCESS] User {email} now has ID = 1")
        
        # Verify the change
        cursor = db.execute("SELECT id, email FROM users WHERE email = ?", (email,))
        updated_user = cursor.fetchone()
        print(f"[VERIFY] {updated_user['email']} has ID = {updated_user['id']}")
        
        return True
        
    except Exception as e:
        print(f"[ERROR] {e}")
        db.rollback()
        return False
    finally:
        db.close()

if __name__ == "__main__":
    target_email = "dmitriy0996@gmail.com"
    print(f"Setting ID = 1 for user {target_email}\n")
    
    success = set_user_id_to_one(target_email)
    
    if success:
        print(f"\n[SUCCESS] Operation completed successfully!")
    else:
        print(f"\n[ERROR] Operation failed")
        sys.exit(1)
