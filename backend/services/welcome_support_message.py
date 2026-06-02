"""Приветственное сообщение от поддержки после регистрации."""

import logging

from config import Config
from models.message import Message
from models.user import get_user_by_id

logger = logging.getLogger(__name__)

SUPPORT_USER_ID = Config.PORTAL_SUPPORT_USER_ID

REGISTRATION_WELCOME_MESSAGE = """Рады видеть вас в клиентском портале Spainza. 

Кратко, что здесь есть:

• Главная — этапы заявки, ключевые документы и быстрый ответ персональному менеджеру (если уже закреплён) или в поддержку.
• Документы — загрузка файлов и ответы на запросы команды.
• Сообщения — переписка с поддержкой и с менеджером.
• Профиль — контактные данные и настройки аккаунта.
• Поддержка — FAQ и связь с командой в случаях сложных вопросов.

Пишите в этот чат при возникновении проблем или вопросов — мы на связи. 
C уважением, команда Spainza."""


def send_support_welcome_to_new_user(connection, new_user_id: int) -> None:
    """Создать чат с поддержкой (если нужно) и отправить приветствие новому пользователю."""
    if not new_user_id:
        return
    uid = int(new_user_id)
    if uid <= 0 or uid == SUPPORT_USER_ID:
        return
    if not get_user_by_id(connection, SUPPORT_USER_ID):
        logger.warning(
            "Support user id=%s not found; skip registration welcome for user_id=%s",
            SUPPORT_USER_ID,
            uid,
        )
        return
    conversation_id = Message.get_or_create_conversation(
        SUPPORT_USER_ID, uid, restore=False
    )
    Message.send_message(
        conversation_id,
        SUPPORT_USER_ID,
        uid,
        message_text=REGISTRATION_WELCOME_MESSAGE,
    )
