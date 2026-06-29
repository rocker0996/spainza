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
    return connection


def initialize_database_schema(connection: sqlite3.Connection) -> None:
    """Create and migrate SQLite schema in one explicit startup step."""
    from models.user import create_users_table, create_manager_clients_table
    from models.document import create_documents_table, ensure_documents_columns
    from models.security_log import create_security_logs_table
    from models.case_data import create_case_data_table
    from models.case_history import create_case_history_table
    from models.case_template import create_manager_case_templates_table
    from models.manager_moderator import create_manager_moderators_table
    from models.message import Message
    from models.notifications import create_notification_tables

    create_users_table(connection)
    create_documents_table(connection)
    ensure_documents_columns(connection)
    create_security_logs_table(connection)
    create_manager_clients_table(connection)
    create_manager_moderators_table(connection)
    create_case_data_table(connection)
    create_case_history_table(connection)
    create_manager_case_templates_table(connection)
    create_notification_tables(connection)
    Message.create_table(connection)
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        INSERT INTO schema_meta (key, value)
        VALUES ('schema_version', '2026-06-29-utc-v1')
        ON CONFLICT(key) DO UPDATE SET value = excluded.value
        """
    )
    connection.commit()
