from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
import unittest


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TelegramQuestionsTest(unittest.TestCase):
    def setUp(self) -> None:
        from models.message import Message
        from models.user import create_users_table

        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        create_users_table(self.db)
        Message.create_table(self.db)
        self.db.execute(
            "INSERT INTO users (id, email, password_hash, name, role_key) VALUES (3, 'support@test', 'x', 'Support', 'support')"
        )
        self.db.execute(
            "INSERT INTO users (id, email, password_hash, name, role_key) VALUES (10, 'client@test', 'x', 'Client', 'client')"
        )
        self.db.commit()

    def tearDown(self) -> None:
        self.db.close()

    def test_state_survives_service_restart_and_update_is_sent_once(self) -> None:
        from models.telegram_conversation import create_telegram_conversation_tables
        from services.telegram_questions import consume_question_text, start_question

        create_telegram_conversation_tables(self.db)
        start_question(self.db, user_id=10, chat_id=700, category="documents")

        first = consume_question_text(
            self.db,
            chat_id=700,
            update_id=77,
            text="Какой перевод нужен?",
            locale="ru",
            support_user_id=3,
        )
        second = consume_question_text(
            self.db,
            chat_id=700,
            update_id=77,
            text="Какой перевод нужен?",
            locale="ru",
            support_user_id=3,
        )

        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(self.db.execute("SELECT COUNT(*) FROM messages").fetchone()[0], 1)

    def test_cancel_removes_active_state(self) -> None:
        from models.telegram_conversation import create_telegram_conversation_tables, get_dialog_state
        from services.telegram_questions import cancel_question, start_question

        create_telegram_conversation_tables(self.db)
        start_question(self.db, user_id=10, chat_id=700, category="other")
        cancel_question(self.db, 700)

        self.assertIsNone(get_dialog_state(self.db, 700))

    def test_schema_bootstrap_creates_dialog_tables(self) -> None:
        from utils.db import initialize_database_schema

        other = sqlite3.connect(":memory:")
        other.row_factory = sqlite3.Row
        try:
            initialize_database_schema(other)
            names = {
                row[0]
                for row in other.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'telegram_%'"
                )
            }
        finally:
            other.close()

        self.assertIn("telegram_dialog_states", names)
        self.assertIn("telegram_processed_updates", names)

    def test_question_view_lists_six_categories(self) -> None:
        from services.telegram_views import build_question_categories_view

        view = build_question_categories_view("ru")
        callbacks = [button.callback_data for row in view.rows for button in row]

        self.assertEqual(
            callbacks[:6],
            [
                "ask:start:documents",
                "ask:start:case",
                "ask:start:payment",
                "ask:start:meeting",
                "ask:start:technical",
                "ask:start:other",
            ],
        )


if __name__ == "__main__":
    unittest.main()
