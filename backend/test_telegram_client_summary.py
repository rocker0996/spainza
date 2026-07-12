from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import sys
import unittest


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TelegramClientSummaryTest(unittest.TestCase):
    def setUp(self) -> None:
        from models.case_data import create_case_data_table
        from models.document import create_documents_table

        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        create_case_data_table(self.db)
        create_documents_table(self.db)

    def tearDown(self) -> None:
        self.db.close()

    def test_collects_rejected_document_and_pending_request(self) -> None:
        from services.telegram_client_summary import load_client_summary

        timeline = [
            {"id": "one", "title": "Анкета", "status": "completed"},
            {"id": "two", "title": "Проверка", "status": "active"},
        ]
        requests = [
            {"id": 7, "name": "Справка", "sent": True, "fulfilled": False, "priority": "urgent"}
        ]
        self.db.execute(
            "INSERT INTO case_data (user_id, timeline_data, document_requests) VALUES (?, ?, ?)",
            (1, json.dumps(timeline), json.dumps(requests)),
        )
        self.db.execute(
            "INSERT INTO documents (user_id, title, status, rejection_comment) VALUES (?, ?, ?, ?)",
            (1, "Договор", "rejected", "Нет последней страницы"),
        )
        self.db.commit()

        summary = load_client_summary(self.db, 1)

        self.assertEqual([task.kind for task in summary.tasks], ["reupload", "upload"])
        self.assertEqual(summary.documents.needs_fix, 1)
        self.assertEqual(summary.case.active_title, "Проверка")

    def test_empty_summary_does_not_invent_stage_or_dates(self) -> None:
        from services.telegram_client_summary import load_client_summary

        summary = load_client_summary(self.db, 22)

        self.assertEqual(summary.tasks, [])
        self.assertIsNone(summary.case.active_title)
        self.assertIsNone(summary.case.updated_at)


if __name__ == "__main__":
    unittest.main()
