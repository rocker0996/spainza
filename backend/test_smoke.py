"""Production smoke tests for the Flask app."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import sys
import tempfile
import unittest


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class AppSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        db_path = Path(self.tmp.name) / "app.db"

        import utils.db as db_utils

        db_utils.get_database_path = lambda: db_path
        os.environ.setdefault("SECRET_KEY", "test-secret-key-for-smoke-tests")

        app_module = importlib.import_module("app")
        self.app = app_module.create_app()
        self.client = self.app.test_client()

    def tearDown(self) -> None:
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


if __name__ == "__main__":
    unittest.main()
