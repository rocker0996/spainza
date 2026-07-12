from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import unittest
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TelegramBotIntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        from models.notifications import upsert_telegram_link
        from utils.db import initialize_database_schema

        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        initialize_database_schema(self.db)
        self.db.execute(
            "INSERT INTO users (id, email, password_hash, name, role_key, locale) VALUES (3, 'support@test', 'x', 'Support', 'support', 'ru')"
        )
        self.db.execute(
            "INSERT INTO users (id, email, password_hash, name, role_key, locale) VALUES (10, 'client@test', 'x', 'Client', 'client', 'ru')"
        )
        self.db.execute(
            "INSERT INTO case_data (user_id, timeline_data, document_requests) VALUES (?, ?, ?)",
            (
                10,
                json.dumps([{"title": "Проверка", "status": "active"}]),
                json.dumps([{"id": 7, "name": "Справка", "sent": True, "fulfilled": False}]),
            ),
        )
        self.db.commit()
        upsert_telegram_link(self.db, 10, 700)

    def tearDown(self) -> None:
        self.db.close()

    def test_linked_client_opens_tasks_and_sends_structured_question(self) -> None:
        from services.telegram_bot import handle_update

        with (
            patch("services.telegram_bot.Config.TELEGRAM_BOT_TOKEN", "token"),
            patch("services.telegram_bot.Config.PORTAL_SUPPORT_USER_ID", 3),
            patch("services.telegram_bot.answer_callback_query"),
            patch("services.telegram_bot.edit_message_text") as edit,
            patch("services.telegram_bot.send_message"),
        ):
            handle_update(
                self.db,
                {"update_id": 1, "callback_query": {"id": "c1", "data": "nav:tasks", "message": {"message_id": 5, "chat": {"id": 700}}}},
            )
            handle_update(
                self.db,
                {"update_id": 2, "callback_query": {"id": "c2", "data": "ask:start:documents", "message": {"message_id": 5, "chat": {"id": 700}}}},
            )
            handle_update(
                self.db,
                {"update_id": 3, "message": {"chat": {"id": 700}, "from": {"id": 70}, "text": "Нужен ли апостиль?"}},
            )

        self.assertGreaterEqual(edit.call_count, 2)
        message = self.db.execute("SELECT message_text FROM messages ORDER BY id DESC LIMIT 1").fetchone()
        self.assertIn("Документы", message["message_text"])
        self.assertIn("Проверка", message["message_text"])
        self.assertIn("Нужен ли апостиль?", message["message_text"])

    def test_guest_personal_section_returns_connection_hint(self) -> None:
        from services.telegram_bot import handle_update

        with (
            patch("services.telegram_bot.Config.TELEGRAM_BOT_TOKEN", "token"),
            patch("services.telegram_bot.answer_callback_query"),
            patch("services.telegram_bot.send_message") as send,
        ):
            handle_update(
                self.db,
                {"update_id": 4, "callback_query": {"id": "c4", "data": "nav:docs", "message": {"message_id": 8, "chat": {"id": 999}}}},
            )

        combined = " ".join(str(call.args[2]) for call in send.call_args_list)
        self.assertIn("подключ", combined.lower())

    def test_start_refreshes_persistent_reply_keyboard(self) -> None:
        from services.telegram_bot import handle_update

        with (
            patch("services.telegram_bot.Config.TELEGRAM_BOT_TOKEN", "token"),
            patch("services.telegram_bot.send_message") as send,
        ):
            handle_update(
                self.db,
                {"update_id": 8, "message": {"chat": {"id": 700}, "from": {"id": 70}, "text": "/start"}},
            )

        markups = [call.kwargs.get("reply_markup") for call in send.call_args_list]
        self.assertTrue(any(markup and "keyboard" in markup for markup in markups))


if __name__ == "__main__":
    unittest.main()
