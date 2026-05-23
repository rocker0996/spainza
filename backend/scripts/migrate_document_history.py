"""Migration script to create document_history table."""

import sqlite3
import sys
import os

# Add parent directory to path to import models
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from models.document_history import create_document_history_table


def main():
    """Run the migration."""
    db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'app.db')
    
    print("Starting document_history table migration...")
    print(f"Database path: {db_path}")
    
    try:
        connection = sqlite3.connect(db_path)
        print("Connected to database")
        
        # Create document_history table
        create_document_history_table(connection)
        print("document_history table created successfully")
        
        connection.close()
        print("Migration completed successfully!")
        
    except Exception as e:
        print(f"Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
