"""Process notification outbox and poll Telegram for bot commands."""

from __future__ import annotations

import sqlite3
import time
from typing import Optional

from config import Config
from models.notifications import (
    fetch_pending_notifications,
    defer_notification_until,
    get_telegram_link_for_user,
    mark_notification_failed,
    mark_notification_sent,
)
from models.telegram_preferences import get_preferences
from services.notification_service import build_telegram_message, lk_url, parse_payload
from services.telegram_api import TelegramApiError, delete_webhook, get_me, get_updates, send_message
from services.telegram_bot import handle_update, setup_bot_ui
from services.telegram_scheduler import (
    build_digest,
    delivery_delay_until,
    reminder_is_relevant,
    schedule_due_reminders,
)
from utils.time import to_storage_datetime, utc_now

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
        processed_ids: set[int] = set()
        for row in rows:
            if int(row["id"]) in processed_ids:
                continue
            preferences = get_preferences(connection, int(row["user_id"]))
            row_payload = parse_payload(row["payload_json"])
            if str(row["event_type"]).startswith("reminder.") and not reminder_is_relevant(
                connection,
                int(row["user_id"]),
                row_payload,
            ):
                mark_notification_sent(connection, int(row["id"]))
                processed += 1
                continue
            if str(row["urgency"] or "normal") != "urgent":
                deliver_at = delivery_delay_until(
                    preferences,
                    utc_now(),
                )
                if deliver_at is not None:
                    defer_notification_until(
                        connection,
                        int(row["id"]),
                        to_storage_datetime(deliver_at),
                    )
                    processed += 1
                    continue
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

            if preferences.digest_enabled and str(row["urgency"] or "normal") != "urgent":
                group = [
                    candidate
                    for candidate in rows
                    if int(candidate["user_id"]) == int(row["user_id"])
                    and str(candidate["urgency"] or "normal") != "urgent"
                ]
                if len(group) > 1:
                    entries: list[tuple[str, str]] = []
                    locale = "ru"
                    for candidate in group:
                        payload = parse_payload(candidate["payload_json"])
                        locale = "en" if str(payload.get("locale") or "ru") == "en" else "ru"
                        item_text, _ = build_telegram_message(str(candidate["event_type"]), payload)
                        lines = [line.strip() for line in item_text.splitlines() if line.strip()]
                        entries.append((lines[0] if lines else "Spainza", " · ".join(lines[1:3])))
                    try:
                        send_message(
                            token,
                            int(link["telegram_chat_id"]),
                            build_digest(locale, entries),
                            reply_markup={
                                "inline_keyboard": [[{
                                    "text": "🏠 " + ("Открыть кабинет" if locale == "ru" else "Open portal"),
                                    "url": lk_url("/frontend/lk/dashboard.html"),
                                }]]
                            },
                        )
                        for candidate in group:
                            mark_notification_sent(connection, int(candidate["id"]))
                            processed_ids.add(int(candidate["id"]))
                            processed += 1
                    except TelegramApiError as exc:
                        for candidate in group:
                            mark_notification_failed(
                                connection,
                                int(candidate["id"]),
                                str(exc),
                                attempts=int(candidate["attempts"]) + 1,
                            )
                            processed_ids.add(int(candidate["id"]))
                            processed += 1
                    continue

            payload = row_payload
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
                try:
                    schedule_due_reminders(connection, utc_now())
                except Exception as exc:
                    print(f"[telegram-worker] scheduler warning: {exc}")
                self.process_outbox(connection)
                self.poll_bot_updates(connection)
            finally:
                connection.close()
            time.sleep(poll_interval_seconds)
