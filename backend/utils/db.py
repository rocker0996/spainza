"""SQLite connection helpers."""

from pathlib import Path
import sqlite3


def get_database_path() -> Path:
    """Return absolute path to /database/app.db."""
    return Path(__file__).resolve().parents[2] / "database" / "app.db"


def get_db_connection() -> sqlite3.Connection:
    """Create a SQLite connection with dict-like row access."""
    db_path = get_database_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    
    # Initialize case_history table if it doesn't exist
    from models.case_history import create_case_history_table
    create_case_history_table(connection)

    from models.case_template import create_manager_case_templates_table
    create_manager_case_templates_table(connection)

    from models.document import ensure_documents_columns
    ensure_documents_columns(connection)

    from models.user import create_manager_clients_table
    from models.manager_moderator import create_manager_moderators_table

    create_manager_clients_table(connection)
    create_manager_moderators_table(connection)

    return connection

