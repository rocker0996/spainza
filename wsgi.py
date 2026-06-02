"""
WSGI entry point for production deployment.

Examples:
  waitress-serve --listen=127.0.0.1:5000 wsgi:application
  gunicorn -w 4 -b 127.0.0.1:5000 wsgi:application
"""

from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR / "backend"))

from bootstrap_sqlite import ensure_bootstrap_users  # noqa: E402

from app import app as application  # noqa: E402

ensure_bootstrap_users()
