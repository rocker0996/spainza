"""Scheduling rules for Telegram reminders and deferred delivery."""

from __future__ import annotations

from datetime import datetime, timedelta
import hashlib
import sqlite3
from zoneinfo import ZoneInfo

from models.notifications import enqueue_notification
from models.telegram_preferences import TelegramPreferences, get_preferences
from services.telegram_client_summary import load_client_summary


EVENT_TASK_REMINDER = "reminder.task_due"
CLIENT_TIMEZONE = ZoneInfo("Europe/Madrid")


def delivery_decision(
    preferences: TelegramPreferences,
    *,
    local_time: str,
    urgency: str = "normal",
) -> str:
    if urgency == "urgent":
        return "send"
    start = preferences.quiet_start
    end = preferences.quiet_end
    if not start or not end:
        return "send"
    if start <= end:
        quiet = start <= local_time < end
    else:
        quiet = local_time >= start or local_time < end
    return "defer" if quiet else "send"


def delivery_delay_until(preferences: TelegramPreferences, now: datetime) -> datetime | None:
    local_now = now.astimezone(CLIENT_TIMEZONE)
    current = local_now.strftime("%H:%M")
    candidates: list[datetime] = []
    if delivery_decision(preferences, local_time=current) == "defer":
        end_hour, end_minute = map(int, str(preferences.quiet_end).split(":"))
        quiet_end = local_now.replace(hour=end_hour, minute=end_minute, second=0, microsecond=0)
        if quiet_end <= local_now:
            quiet_end += timedelta(days=1)
        candidates.append(quiet_end)
    if preferences.digest_enabled:
        digest_hour, digest_minute = map(int, preferences.digest_time.split(":"))
        if not (local_now.hour == digest_hour and local_now.minute == digest_minute):
            digest_at = local_now.replace(hour=digest_hour, minute=digest_minute, second=0, microsecond=0)
            if digest_at <= local_now:
                digest_at += timedelta(days=1)
            candidates.append(digest_at)
    return max(candidates).astimezone(now.tzinfo) if candidates else None


def _stable_task_key(user_id: int, kind: str, title: str, due_at: str, offset: int) -> str:
    raw = f"{user_id}:{kind}:{title}:{due_at}:{offset}".encode("utf-8")
    return "reminder:" + hashlib.sha256(raw).hexdigest()[:32]


def schedule_due_reminders(connection: sqlite3.Connection, now: datetime) -> int:
    rows = connection.execute(
        "SELECT user_id FROM user_telegram_links WHERE is_active = 1 ORDER BY user_id"
    ).fetchall()
    scheduled = 0
    today = now.date()
    for row in rows:
        user_id = int(row["user_id"])
        if not get_preferences(connection, user_id).reminders:
            continue
        summary = load_client_summary(connection, user_id)
        for task in summary.tasks:
            if not task.due_at:
                continue
            try:
                due_date = datetime.fromisoformat(task.due_at[:10]).date()
            except ValueError:
                continue
            offset = (due_date - today).days
            if offset not in {3, 0, -1}:
                continue
            notification_id = enqueue_notification(
                connection,
                user_id,
                EVENT_TASK_REMINDER,
                {
                    "task_kind": task.kind,
                    "title": task.title,
                    "due_at": task.due_at,
                    "offset_days": offset,
                },
                dedupe_key=_stable_task_key(user_id, task.kind, task.title, task.due_at, offset),
                urgency="urgent" if offset <= 0 else "normal",
            )
            if notification_id:
                scheduled += 1
    return scheduled


def reminder_is_relevant(connection: sqlite3.Connection, user_id: int, payload: dict) -> bool:
    kind = str(payload.get("task_kind") or "")
    title = str(payload.get("title") or "")
    due_at = str(payload.get("due_at") or "")
    return any(
        task.kind == kind and task.title == title and str(task.due_at or "") == due_at
        for task in load_client_summary(connection, user_id).tasks
    )


def build_digest(locale: str, entries: list[tuple[str, str]]) -> str:
    ru = locale == "ru"
    lines = [
        f"📬 {'Сводка Spainza' if ru else 'Spainza digest'} · {len(entries)}",
        "",
    ]
    for title, detail in entries:
        line = f"• {title}"
        if detail:
            line += f": {detail}"
        lines.append(line)
    return "\n".join(lines)
