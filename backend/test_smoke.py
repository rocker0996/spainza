"""Production smoke tests for the Flask app."""

from __future__ import annotations

import importlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from datetime import timedelta

from werkzeug.datastructures import FileStorage


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class AppSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.old_cwd = os.getcwd()
        os.chdir(self.tmp.name)
        db_path = Path(self.tmp.name) / "app.db"

        import utils.db as db_utils

        db_utils.get_database_path = lambda: db_path
        os.environ.setdefault("SECRET_KEY", "test-secret-key-for-smoke-tests")

        app_module = importlib.import_module("app")
        self.app = app_module.create_app()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
        os.chdir(self.old_cwd)
        self.tmp.cleanup()

    def test_health_check(self) -> None:
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"status": "ok"})

    def test_protected_api_requires_token(self) -> None:
        protected_paths = (
            "/api/application/progress",
            "/api/documents",
            "/api/conversations",
            "/api/user",
        )
        for path in protected_paths:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.get_json()["error"], "missing token")

    def test_message_file_preserves_cyrillic_display_name(self) -> None:
        from services.file_service import FileService

        service = FileService()
        upload = FileStorage(
            stream=io.BytesIO(b"%PDF-1.4\n%test\n"),
            filename="Отчёт ВНЖ.pdf",
            content_type="application/pdf",
        )

        relative_path, display_name = service.save_message_file(upload, user_id=7)

        self.assertTrue(relative_path.startswith("messages/7/"))
        self.assertEqual(display_name, "Отчёт ВНЖ.pdf")
        self.assertTrue(Path(service.get_file_path(relative_path)).exists())

    def test_retention_cleanup_removes_expired_payload_files(self) -> None:
        from services.file_retention import cleanup_expired_files
        from services.file_service import FileService
        from utils.db import get_db_connection
        from utils.time import to_storage_datetime, utc_now

        db = get_db_connection()
        service = FileService()
        now = utc_now()

        message_dir = Path(service.get_file_path("messages/1"))
        document_dir = Path(service.get_file_path("documents/2/general"))
        archive_dir = Path(service.get_file_path("documents/2/case-archive"))
        message_dir.mkdir(parents=True, exist_ok=True)
        document_dir.mkdir(parents=True, exist_ok=True)
        archive_dir.mkdir(parents=True, exist_ok=True)
        message_file = message_dir / "old.pdf"
        document_file = document_dir / "doc.pdf"
        archive_file = archive_dir / "archive.zip"
        for path in (message_file, document_file, archive_file):
            path.write_bytes(b"%PDF-1.4\n")

        db.execute(
            """
            INSERT INTO messages (
                conversation_id, sender_id, receiver_id, message_text, file_path,
                file_name, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "conv_1_2",
                1,
                2,
                "",
                "messages/1/old.pdf",
                "old.pdf",
                to_storage_datetime(now - timedelta(days=91)),
            ),
        )
        db.execute(
            """
            INSERT INTO case_data (
                user_id, visa_type, archive_file_path, archive_file_name,
                timeline_data, document_requests, completed_at, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "digital_nomad",
                "documents/2/case-archive/archive.zip",
                "archive.zip",
                "[]",
                "[]",
                to_storage_datetime(now - timedelta(days=31)),
                to_storage_datetime(now - timedelta(days=40)),
                to_storage_datetime(now - timedelta(days=40)),
            ),
        )
        db.execute(
            """
            INSERT INTO documents (
                user_id, title, file_path, file_type, file_size, last_action_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                2,
                "Doc",
                "documents/2/general/doc.pdf",
                "PDF",
                "1 KB",
                to_storage_datetime(now - timedelta(days=40)),
                to_storage_datetime(now - timedelta(days=40)),
            ),
        )
        db.commit()

        counts = cleanup_expired_files(db, file_service=service)

        self.assertEqual(counts["chat_messages"], 1)
        self.assertEqual(counts["case_documents"], 1)
        self.assertEqual(counts["case_archives"], 1)
        self.assertFalse(message_file.exists())
        self.assertFalse(document_file.exists())
        self.assertFalse(archive_file.exists())
        message_row = db.execute("SELECT file_path, file_name FROM messages").fetchone()
        document_row = db.execute("SELECT file_path FROM documents").fetchone()
        case_row = db.execute("SELECT archive_file_path, retention_cleanup_at FROM case_data").fetchone()
        self.assertIsNone(message_row["file_path"])
        self.assertIsNone(message_row["file_name"])
        self.assertIsNone(document_row["file_path"])
        self.assertIsNone(case_row["archive_file_path"])
        self.assertTrue(case_row["retention_cleanup_at"])
        db.close()


if __name__ == "__main__":
    unittest.main()
