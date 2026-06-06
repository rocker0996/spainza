"""Enqueue and format portal notifications for Telegram delivery."""

from __future__ import annotations

import json
import sqlite3
from typing import Any, Optional

from config import Config
from models.application_progress import ApplicationProgress
from models.notifications import (
    enqueue_notification,
    get_telegram_link_for_user,
)
from models.user import get_user_by_id


EVENT_MESSAGE_RECEIVED = "message.received"
EVENT_DOCUMENT_REQUEST_SENT = "document_request.sent"
EVENT_DOCUMENT_APPROVED = "document.approved"
EVENT_DOCUMENT_REJECTED = "document.rejected"
EVENT_CASE_TIMELINE_STATUS = "case.timeline_status_changed"
EVENT_CASE_STAGE_CHANGED = "case.stage_changed"

TIMELINE_STATUS_LABELS = {
    "ru": {
        "completed": "завершён",
        "active": "активен",
        "pending": "ожидание",
    },
    "en": {
        "completed": "completed",
        "active": "active",
        "pending": "pending",
    },
}


def _user_locale(connection: sqlite3.Connection, user_id: int) -> str:
    user = get_user_by_id(connection, user_id)
    if not user:
        return "ru"
    locale = str(user["locale"] or "ru").strip().lower()
    return "en" if locale == "en" else "ru"


def _user_notify_telegram_enabled(connection: sqlite3.Connection, user_id: int) -> bool:
    user = get_user_by_id(connection, user_id)
    if not user:
        return False
    if not bool(user["notify_telegram"]):
        return False
    return get_telegram_link_for_user(connection, user_id) is not None


def notify(
    connection: sqlite3.Connection,
    user_id: int,
    event_type: str,
    context: dict[str, Any],
) -> Optional[int]:
    """Queue a Telegram notification if the user opted in and linked Telegram."""
    if not _user_notify_telegram_enabled(connection, user_id):
        return None
    payload = dict(context)
    payload["locale"] = _user_locale(connection, user_id)
    notification_id = enqueue_notification(connection, user_id, event_type, payload)
    if notification_id:
        try:
            from services.telegram_worker import process_notification_outbox

            process_notification_outbox(connection, batch_size=10)
        except Exception:
            pass
    return notification_id


def portal_base_url() -> str:
    base = (Config.PUBLIC_BASE_URL or "").strip().rstrip("/")
    if base:
        return base
    return f"http://{Config.FLASK_RUN_HOST}:{Config.FLASK_RUN_PORT}"


def lk_url(path: str) -> str:
    normalized = path if path.startswith("/") else f"/{path}"
    return f"{portal_base_url()}{normalized}"


def detect_timeline_status_changes(
    old_steps: list,
    new_steps: list,
) -> list[dict[str, str]]:
    """Return timeline steps whose status changed between saves."""
    old_list = [x for x in (old_steps or []) if isinstance(x, dict)]
    new_list = [x for x in (new_steps or []) if isinstance(x, dict)]

    def key_of(step: dict, index: int) -> str:
        raw_id = step.get("id")
        if raw_id is not None and str(raw_id).strip() != "":
            return f"id:{raw_id}"
        title = str(step.get("title") or "").strip().lower()
        return f"idx:{index}:{title}"

    old_map = {key_of(step, i): step for i, step in enumerate(old_list)}
    new_map = {key_of(step, i): step for i, step in enumerate(new_list)}
    changes: list[dict[str, str]] = []

    for key in sorted(set(old_map) & set(new_map)):
        old_status = str(old_map[key].get("status") or "pending").strip().lower()
        new_status = str(new_map[key].get("status") or "pending").strip().lower()
        if old_status == new_status:
            continue
        title = str(new_map[key].get("title") or old_map[key].get("title") or "").strip()
        changes.append(
            {
                "step_title": title or "—",
                "old_status": old_status,
                "new_status": new_status,
            }
        )
    return changes


def stage_title(application_type: str, stage_id: str, locale: str) -> str:
    stages = ApplicationProgress.get_stages_for_type(application_type or "vnj_investment")
    for stage in stages:
        if stage.stage_id == stage_id:
            return stage.title_en if locale == "en" else stage.title_ru
    return stage_id


def build_telegram_message(
    event_type: str,
    payload: dict[str, Any],
) -> tuple[str, Optional[dict[str, Any]]]:
    locale = "en" if str(payload.get("locale") or "ru").lower() == "en" else "ru"
    ru = locale == "ru"
    buttons: list[list[dict[str, str]]] = []

    if event_type == EVENT_MESSAGE_RECEIVED:
        sender = str(payload.get("sender_name") or ("Менеджер" if ru else "Manager")).strip()
        preview = str(payload.get("preview") or "").strip()
        if len(preview) > 280:
            preview = preview[:277] + "..."
        if payload.get("has_attachment"):
            attachment = "📎 Вложение" if ru else "📎 Attachment"
            preview = preview or attachment
        text = (
            f"💬 {'Новое сообщение' if ru else 'New message'}\n\n"
            f"{'От' if ru else 'From'}: {sender}\n"
            f"{preview}"
        )
        buttons.append(
            [{"text": "💬 " + ("Открыть чат" if ru else "Open chat"), "url": lk_url("/frontend/lk/messages.html")}]
        )

    elif event_type == EVENT_DOCUMENT_REQUEST_SENT:
        names = payload.get("request_names") or []
        if not isinstance(names, list):
            names = []
        lines = "\n".join(f"• {name}" for name in names[:8])
        urgent = bool(payload.get("urgent"))
        header = "📄 " + ("Запрос документов" if ru else "Document request")
        if urgent:
            header += " ⚠️ " + ("СРОЧНО" if ru else "URGENT")
        editor = str(payload.get("editor_name") or "").strip()
        text = header
        if editor:
            text += f"\n\n{'От' if ru else 'From'}: {editor}"
        text += f"\n\n{lines or ('—' if ru else '—')}"
        buttons.append(
            [
                {
                    "text": "📎 " + ("Загрузить" if ru else "Upload"),
                    "url": lk_url("/frontend/lk/documents.html"),
                }
            ]
        )

    elif event_type == EVENT_DOCUMENT_APPROVED:
        title = str(payload.get("document_title") or "—").strip()
        text = (
            f"✅ {'Документ одобрен' if ru else 'Document approved'}\n\n"
            f"«{title}»"
        )
        buttons.append(
            [{"text": "📁 " + ("Документы" if ru else "Documents"), "url": lk_url("/frontend/lk/documents.html")}]
        )

    elif event_type == EVENT_DOCUMENT_REJECTED:
        title = str(payload.get("document_title") or "—").strip()
        comment = str(payload.get("rejection_comment") or "").strip()
        if len(comment) > 400:
            comment = comment[:397] + "..."
        text = (
            f"❌ {'Документ отклонён' if ru else 'Document rejected'}\n\n"
            f"«{title}»"
        )
        if comment:
            text += f"\n\n{'Причина' if ru else 'Reason'}:\n{comment}"
        buttons.append(
            [
                {
                    "text": "🔄 " + ("Загрузить заново" if ru else "Re-upload"),
                    "url": lk_url("/frontend/lk/documents.html"),
                }
            ]
        )

    elif event_type == EVENT_CASE_TIMELINE_STATUS:
        step_title = str(payload.get("step_title") or "—").strip()
        labels = TIMELINE_STATUS_LABELS[locale]
        old_status = labels.get(str(payload.get("old_status") or ""), str(payload.get("old_status") or "—"))
        new_status = labels.get(str(payload.get("new_status") or ""), str(payload.get("new_status") or "—"))
        text = (
            f"📊 {'Статус кейса изменён' if ru else 'Case status updated'}\n\n"
            f"{'Шаг' if ru else 'Step'}: «{step_title}»\n"
            f"{old_status} → {new_status}"
        )
        buttons.append(
            [{"text": "📋 " + ("Кейс" if ru else "Case"), "url": lk_url("/frontend/lk/case.html")}]
        )

    elif event_type == EVENT_CASE_STAGE_CHANGED:
        stage_name = str(payload.get("stage_title") or payload.get("stage_id") or "—").strip()
        text = (
            f"🚀 {'Этап заявки обновлён' if ru else 'Application stage updated'}\n\n"
            f"{stage_name}"
        )
        buttons.append(
            [{"text": "🏠 " + ("Кабинет" if ru else "Dashboard"), "url": lk_url("/frontend/lk/dashboard.html")}]
        )

    else:
        text = "🔔 Spainza: " + ("Новое уведомление" if ru else "New notification")

    reply_markup = {"inline_keyboard": buttons} if buttons else None
    return text, reply_markup


def parse_payload(raw: str) -> dict[str, Any]:
    try:
        data = json.loads(raw or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}
