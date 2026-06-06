"""Process notification outbox and poll Telegram for bot commands."""

from __future__ import annotations

import sqlite3
import time
from typing import Optional

from config import Config
from models.notifications import (
    fetch_pending_notifications,
    get_telegram_link_for_user,
    mark_notification_failed,
    mark_notification_sent,
)
from services.notification_service import build_telegram_message, parse_payload
from services.telegram_api import TelegramApiError, delete_webhook, get_me, get_updates, send_message
from services.telegram_bot import handle_update, setup_bot_ui

_worker_singleton: Optional["TelegramWorker"] = None


def process_notification_outbox(
    connection: sqlite3.Connection,
    *,
    batch_size: int = 20,
) -> int:
    """Send pending outbox rows immediately (best-effort)."""
    global _worker_singleton
    if not Config.TELEGRAM_BOT_TOKEN:
        return 0
    if _worker_singleton is None:
        _worker_singleton = TelegramWorker()
    return _worker_singleton.process_outbox(connection, batch_size=batch_size)


class TelegramWorker:
    def __init__(self) -> None:
        self._offset: Optional[int] = None
        self._bot_username = ""

    def ensure_bot_identity(self) -> None:
        token = Config.TELEGRAM_BOT_TOKEN
        if not token:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not set")
        try:
            delete_webhook(token)
        except TelegramApiError as exc:
            print(f"[telegram-worker] deleteWebhook warning: {exc}")
        me = get_me(token)
        self._bot_username = str(me.get("username") or "").strip()
        setup_bot_ui(token)

    def process_outbox(self, connection: sqlite3.Connection, *, batch_size: int = 20) -> int:
        token = Config.TELEGRAM_BOT_TOKEN
        if not token:
            return 0

        rows = fetch_pending_notifications(connection, limit=batch_size)
        processed = 0
        for row in rows:
            link = get_telegram_link_for_user(connection, int(row["user_id"]))
            if not link:
                mark_notification_failed(
                    connection,
                    int(row["id"]),
                    "telegram not linked",
                    attempts=int(row["attempts"]) + 1,
                )
                processed += 1
                continue

            payload = parse_payload(row["payload_json"])
            text, reply_markup = build_telegram_message(str(row["event_type"]), payload)
            try:
                send_message(
                    token,
                    int(link["telegram_chat_id"]),
                    text,
                    reply_markup=reply_markup,
                )
                mark_notification_sent(connection, int(row["id"]))
            except TelegramApiError as exc:
                mark_notification_failed(
                    connection,
                    int(row["id"]),
                    str(exc),
                    attempts=int(row["attempts"]) + 1,
                )
            processed += 1
        return processed

    def poll_bot_updates(self, connection: sqlite3.Connection) -> int:
        token = Config.TELEGRAM_BOT_TOKEN
        if not token:
            return 0

        updates = get_updates(token, offset=self._offset, timeout=25)
        handled = 0
        for update in updates:
            update_id = int(update.get("update_id", 0))
            if self._offset is None or update_id >= self._offset:
                self._offset = update_id + 1
            try:
                handle_update(connection, update, bot_username=self._bot_username)
            except Exception as exc:
                print(f"[telegram-bot] update error: {exc}")
            handled += 1
        return handled

    def run_forever(
        self,
        connection_factory,
        *,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        while not self._bot_username:
            try:
                self.ensure_bot_identity()
                print(f"[telegram-worker] bot @{self._bot_username or '?'} ready")
            except Exception as exc:
                print(f"[telegram-worker] startup failed, retry in 15s: {exc}")
                time.sleep(15)
        while True:
            connection = connection_factory()
            try:
                self.process_outbox(connection)
                self.poll_bot_updates(connection)
            finally:
                connection.close()
            time.sleep(poll_interval_seconds)
