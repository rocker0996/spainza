from __future__ import annotations

from pathlib import Path
import sqlite3
import sys
import unittest


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TelegramNotificationsTest(unittest.TestCase):
    def setUp(self) -> None:
        from models.notifications import create_notification_tables, upsert_telegram_link
        from models.user import create_users_table

        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        create_users_table(self.db)
        create_notification_tables(self.db)
        self.db.execute(
            "INSERT INTO users (id, email, password_hash, locale, notify_telegram) VALUES (10, 'client@test', 'x', 'ru', 1)"
        )
        self.db.commit()
        upsert_telegram_link(self.db, 10, 700)

    def tearDown(self) -> None:
        self.db.close()

    def test_rejection_notification_has_reason_and_reupload_actions(self) -> None:
        from services.notification_service import EVENT_DOCUMENT_REJECTED, build_telegram_message

        _, markup = build_telegram_message(
            EVENT_DOCUMENT_REJECTED,
            {"locale": "ru", "document_title": "Договор", "rejection_comment": "Нет страницы"},
        )
        labels = [button["text"] for row in markup["inline_keyboard"] for button in row]

        self.assertEqual(labels, ["❌ Посмотреть причину", "🔄 Загрузить заново"])

    def test_disabled_document_category_suppresses_telegram_event(self) -> None:
        from models.telegram_preferences import create_telegram_preferences_table, update_preferences
        from services.notification_service import EVENT_DOCUMENT_APPROVED, notify

        create_telegram_preferences_table(self.db)
        update_preferences(self.db, 10, documents=False)

        event_id = notify(self.db, 10, EVENT_DOCUMENT_APPROVED, {"document_title": "Паспорт"})

        self.assertIsNone(event_id)

    def test_settings_view_exposes_category_and_language_toggles(self) -> None:
        from models.telegram_preferences import TelegramPreferences
        from services.telegram_views import build_settings_view

        view = build_settings_view("ru", TelegramPreferences(user_id=10))
        callbacks = [button.callback_data for row in view.rows for button in row]

        self.assertIn("set:documents:0", callbacks)
        self.assertIn("set:messages:0", callbacks)
        self.assertIn("set:lang:en", callbacks)


if __name__ == "__main__":
    unittest.main()
