"""Per-user Telegram delivery preferences."""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3
from typing import Optional


@dataclass(frozen=True)
class TelegramPreferences:
    user_id: int
    locale: Optional[str] = None
    messages: bool = True
    documents: bool = True
    case_updates: bool = True
    reminders: bool = True
    quiet_start: Optional[str] = None
    quiet_end: Optional[str] = None
    digest_enabled: bool = False
    digest_time: str = "09:00"


ALLOWED_FIELDS = {
    "locale",
    "messages",
    "documents",
    "case_updates",
    "reminders",
    "quiet_start",
    "quiet_end",
    "digest_enabled",
    "digest_time",
}


def create_telegram_preferences_table(connection: sqlite3.Connection) -> None:
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_preferences (
            user_id INTEGER PRIMARY KEY,
            locale TEXT,
            messages INTEGER NOT NULL DEFAULT 1,
            documents INTEGER NOT NULL DEFAULT 1,
            case_updates INTEGER NOT NULL DEFAULT 1,
            reminders INTEGER NOT NULL DEFAULT 1,
            quiet_start TEXT,
            quiet_end TEXT,
            digest_enabled INTEGER NOT NULL DEFAULT 0,
            digest_time TEXT NOT NULL DEFAULT '09:00',
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    connection.commit()


def get_preferences(connection: sqlite3.Connection, user_id: int) -> TelegramPreferences:
    create_telegram_preferences_table(connection)
    row = connection.execute("SELECT * FROM telegram_preferences WHERE user_id = ?", (user_id,)).fetchone()
    if not row:
        return TelegramPreferences(user_id=user_id)
    return TelegramPreferences(
        user_id=user_id,
        locale=row["locale"],
        messages=bool(row["messages"]),
        documents=bool(row["documents"]),
        case_updates=bool(row["case_updates"]),
        reminders=bool(row["reminders"]),
        quiet_start=row["quiet_start"],
        quiet_end=row["quiet_end"],
        digest_enabled=bool(row["digest_enabled"]),
        digest_time=str(row["digest_time"] or "09:00"),
    )


def update_preferences(connection: sqlite3.Connection, user_id: int, **changes) -> TelegramPreferences:
    create_telegram_preferences_table(connection)
    invalid = set(changes) - ALLOWED_FIELDS
    if invalid:
        raise ValueError(f"unsupported Telegram preference: {sorted(invalid)[0]}")
    current = get_preferences(connection, user_id)
    values = current.__dict__ | changes
    connection.execute(
        """
        INSERT INTO telegram_preferences (
            user_id, locale, messages, documents, case_updates, reminders,
            quiet_start, quiet_end, digest_enabled, digest_time
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            locale=excluded.locale, messages=excluded.messages, documents=excluded.documents,
            case_updates=excluded.case_updates, reminders=excluded.reminders,
            quiet_start=excluded.quiet_start, quiet_end=excluded.quiet_end,
            digest_enabled=excluded.digest_enabled, digest_time=excluded.digest_time
        """,
        (
            user_id,
            values["locale"],
            int(bool(values["messages"])),
            int(bool(values["documents"])),
            int(bool(values["case_updates"])),
            int(bool(values["reminders"])),
            values["quiet_start"],
            values["quiet_end"],
            int(bool(values["digest_enabled"])),
            values["digest_time"],
        ),
    )
    connection.commit()
    return get_preferences(connection, user_id)
