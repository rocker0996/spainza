"""Account deletion request flow: soft-delete for user, support confirmation in chat."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from config import Config
from models.message import Message
from models.user import (
    get_role_definition,
    get_user_by_id,
    normalize_role_key,
)

logger = logging.getLogger(__name__)

SUPPORT_USER_ID = Config.PORTAL_SUPPORT_USER_ID
ACCOUNT_DELETION_MESSAGE_PREFIX = "[[SPAINZA_ACCOUNT_DELETION]]"


def build_account_deletion_request_message(user: Any, when_label: str) -> str:
    """Structured message for support chat with embedded user id for staff actions."""
    uid = int(user["id"])
    display_id = str(user["display_id"] or "—").strip() or "—"
    name = str(user["name"] or "").strip() or "—"
    email = str(user["email"] or "").strip() or "—"
    phone = str(user["phone"] or "").strip() or "—"
    role_key = normalize_role_key(user["role_key"] or "")
    role = get_role_definition(role_key)

    return (
        f"{ACCOUNT_DELETION_MESSAGE_PREFIX}\n"
        f"[[USER_ID:{uid}]]\n"
        f"[[DISPLAY_ID:{display_id}]]\n\n"
        f"[ЗАПРОС НА УДАЛЕНИЕ АККАУНТА]\n\n"
        f"Дата и время: {when_label}\n\n"
        f"— Пользователь —\n"
        f"Внутренний ID: {uid}\n"
        f"Публичный ID: {display_id}\n"
        f"Имя в профиле: {name}\n"
        f"Email: {email}\n"
        f"Телефон: {phone}\n"
        f"Роль (ключ): {role_key}\n"
        f"Роль (отображение): {role.get('name_ru') or '—'}\n\n"
        f"Пользователь подтвердил удаление паролем (дважды).\n"
        f"Аккаунт заблокирован для входа до решения поддержки.\n\n"
        f"Действия:\n"
        f"• Подтвердить удаление — безвозвратно удалить аккаунт\n"
        f"• Восстановить — отменить запрос, пользователь снова сможет войти"
    )


def send_account_deletion_request_to_support(connection, user_id: int) -> None:
    """Create/restore support chat and post the deletion request from the user."""
    if not user_id:
        return
    uid = int(user_id)
    if uid <= 0 or uid == SUPPORT_USER_ID:
        return
    user = get_user_by_id(connection, uid)
    if not user:
        return
    if not get_user_by_id(connection, SUPPORT_USER_ID):
        logger.warning(
            "Support user id=%s not found; skip deletion request for user_id=%s",
            SUPPORT_USER_ID,
            uid,
        )
        return

    when_label = datetime.now().strftime("%d.%m.%Y %H:%M")
    message_text = build_account_deletion_request_message(user, when_label)
    conversation_id = Message.get_or_create_conversation(SUPPORT_USER_ID, uid, restore=True)
    Message.send_message(
        conversation_id,
        uid,
        SUPPORT_USER_ID,
        message_text=message_text,
    )
