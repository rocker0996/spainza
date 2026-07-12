from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import sys
import unittest


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TelegramSchedulerTest(unittest.TestCase):
    def setUp(self) -> None:
        from models.case_data import create_case_data_table
        from models.document import create_documents_table
        from models.notifications import create_notification_tables, upsert_telegram_link
        from models.telegram_preferences import create_telegram_preferences_table
        from models.user import create_users_table

        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        create_users_table(self.db)
        create_documents_table(self.db)
        create_case_data_table(self.db)
        create_notification_tables(self.db)
        create_telegram_preferences_table(self.db)
        self.db.execute(
            "INSERT INTO users (id, email, password_hash, locale, notify_telegram) VALUES (10, 'client@test', 'x', 'ru', 1)"
        )
        self.db.commit()
        upsert_telegram_link(self.db, 10, 700)

    def tearDown(self) -> None:
        self.db.close()

    def test_quiet_hours_defer_normal_but_not_urgent(self) -> None:
        from models.telegram_preferences import TelegramPreferences
        from services.telegram_scheduler import delivery_decision

        preferences = TelegramPreferences(user_id=10, quiet_start="22:00", quiet_end="08:00")

        self.assertEqual(delivery_decision(preferences, local_time="23:00", urgency="normal"), "defer")
        self.assertEqual(delivery_decision(preferences, local_time="23:00", urgency="urgent"), "send")

    def test_due_reminder_is_scheduled_once(self) -> None:
        from services.telegram_scheduler import schedule_due_reminders

        requests = [{"id": 7, "name": "Справка", "sent": True, "fulfilled": False, "deadline": "2026-07-15"}]
        self.db.execute(
            "INSERT INTO case_data (user_id, document_requests) VALUES (?, ?)",
            (10, json.dumps(requests)),
        )
        self.db.commit()
        now = datetime(2026, 7, 12, 8, 0, tzinfo=timezone.utc)

        self.assertEqual(schedule_due_reminders(self.db, now), 1)
        self.assertEqual(schedule_due_reminders(self.db, now), 0)

    def test_reminder_message_has_task_action(self) -> None:
        from services.notification_service import build_telegram_message
        from services.telegram_scheduler import EVENT_TASK_REMINDER

        text, markup = build_telegram_message(
            EVENT_TASK_REMINDER,
            {"locale": "ru", "title": "Справка", "due_at": "2026-07-15", "offset_days": 3},
        )

        self.assertIn("Справка", text)
        self.assertEqual(markup["inline_keyboard"][0][0]["text"], "✅ Открыть задачу")

    def test_digest_combines_multiple_events(self) -> None:
        from services.telegram_scheduler import build_digest

        text = build_digest("ru", [("Документ одобрен", "Паспорт"), ("Новый этап", "Подача")])

        self.assertIn("2", text)
        self.assertIn("Паспорт", text)
        self.assertIn("Подача", text)

    def test_quiet_hours_return_future_delivery_time(self) -> None:
        from models.telegram_preferences import TelegramPreferences
        from services.telegram_scheduler import delivery_delay_until

        now = datetime(2026, 7, 12, 21, 0, tzinfo=timezone.utc)
        preferences = TelegramPreferences(user_id=10, quiet_start="22:00", quiet_end="08:00")

        deliver_at = delivery_delay_until(preferences, now)

        self.assertIsNotNone(deliver_at)
        self.assertGreater(deliver_at, now)

    def test_reminder_becomes_irrelevant_after_task_completion(self) -> None:
        from services.telegram_scheduler import reminder_is_relevant

        requests = [{"id": 9, "name": "Страховка", "sent": True, "fulfilled": False, "deadline": "2026-07-15"}]
        self.db.execute(
            "INSERT INTO case_data (user_id, document_requests) VALUES (?, ?)",
            (10, json.dumps(requests)),
        )
        self.db.commit()
        payload = {"task_kind": "upload", "title": "Страховка", "due_at": "2026-07-15"}
        self.assertTrue(reminder_is_relevant(self.db, 10, payload))

        requests[0]["fulfilled"] = True
        self.db.execute("UPDATE case_data SET document_requests = ? WHERE user_id = 10", (json.dumps(requests),))
        self.db.commit()

        self.assertFalse(reminder_is_relevant(self.db, 10, payload))


if __name__ == "__main__":
    unittest.main()
