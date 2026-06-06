#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run Telegram notification worker (outbox + bot polling)."""

import os
import sys
from pathlib import Path

if sys.platform == "win32":
    import codecs

    sys.stdout = codecs.getwriter("utf-8")(sys.stdout.buffer, "strict")
    sys.stderr = codecs.getwriter("utf-8")(sys.stderr.buffer, "strict")

ROOT_DIR = Path(__file__).parent.resolve()
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(ROOT_DIR))
sys.path.insert(0, str(BACKEND_DIR))


def _load_dotenv() -> None:
    env_path = ROOT_DIR / ".env"
    if not env_path.is_file():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> None:
    _load_dotenv()

    from config import Config
    from models.notifications import create_notification_tables
    from models.user import create_users_table
    from services.telegram_worker import TelegramWorker
    from utils.db import get_db_connection

    if not Config.TELEGRAM_BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN is not set. Telegram worker is disabled.")
        sys.exit(0)

    bootstrap = get_db_connection()
    try:
        create_users_table(bootstrap)
        create_notification_tables(bootstrap)
    finally:
        bootstrap.close()

    print("=" * 60)
    print("Telegram worker (outbox + bot polling)")
    print("=" * 60)
    print("Stop with Ctrl+C")
    print()

    worker = TelegramWorker()
    worker.run_forever(get_db_connection, poll_interval_seconds=2.0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nTelegram worker stopped.")
