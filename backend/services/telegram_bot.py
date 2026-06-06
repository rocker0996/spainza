"""Telegram bot handlers: menus, buttons, and account linking."""

from __future__ import annotations

import re
import sqlite3
import time
from typing import Any, Optional

from config import Config
from models.case_data import count_sent_document_requests, get_case_data_by_user_id
from models.notifications import (
    complete_telegram_login_session,
    consume_telegram_link_code,
    consume_telegram_login_session,
    deactivate_telegram_link,
    get_telegram_link_for_user,
    upsert_telegram_link,
)
from models.user import get_user_by_id
from services.telegram_login import resolve_or_create_user_from_telegram
from services.notification_service import lk_url
from services.telegram_api import answer_callback_query, send_message, set_my_commands

START_CODE_RE = re.compile(r"^/start(?:@\w+)?(?:\s+(\d{6}))?\s*$", re.IGNORECASE)
LOGIN_START_CODE_RE = re.compile(
    r"^/start(?:@\w+)?\s+(login\d{6})\s*$",
    re.IGNORECASE,
)

CB_STATUS = "menu:status"
CB_HELP = "menu:help"
CB_UNLINK = "menu:unlink"
CB_UNLINK_YES = "menu:unlink_yes"
CB_UNLINK_NO = "menu:unlink_no"
CB_CONNECT = "menu:connect"

MENU_TEXT_ACTIONS = {
    "📌 Статус кейса": "status",
    "📌 Case status": "status",
    "🏠 Кабинет": "portal",
    "🏠 Portal": "portal",
    "❓ Помощь": "help",
    "❓ Help": "help",
    "🔕 Отключить": "unlink",
    "🔕 Disconnect": "unlink",
    "🔗 Как подключить": "connect",
    "🔗 How to connect": "connect",
}


def setup_bot_ui(token: str) -> None:
    """Register slash-command hints shown in the Telegram menu."""
    if not token:
        return
    try:
        set_my_commands(
            token,
            [
                {"command": "start", "description": "Главное меню"},
                {"command": "status", "description": "Статус кейса"},
                {"command": "help", "description": "Справка и кнопки"},
            ],
            language_code="ru",
        )
        set_my_commands(
            token,
            [
                {"command": "start", "description": "Main menu"},
                {"command": "status", "description": "Case status"},
                {"command": "help", "description": "Help and buttons"},
            ],
            language_code="en",
        )
    except Exception as exc:
        print(f"[telegram-bot] setup menu warning: {exc}")


def _locale_for_user(connection: sqlite3.Connection, user_id: int) -> str:
    user = get_user_by_id(connection, user_id)
    if not user:
        return "ru"
    return "en" if str(user["locale"] or "ru").strip().lower() == "en" else "ru"


def _linked_user_id_for_chat(connection: sqlite3.Connection, chat_id: int) -> Optional[int]:
    row = connection.execute(
        """
        SELECT user_id
        FROM user_telegram_links
        WHERE telegram_chat_id = ? AND is_active = 1
        LIMIT 1
        """,
        (chat_id,),
    ).fetchone()
    return int(row["user_id"]) if row else None


def _is_ru_for_chat(connection: sqlite3.Connection, chat_id: int) -> bool:
    user_id = _linked_user_id_for_chat(connection, chat_id)
    if not user_id:
        return True
    return _locale_for_user(connection, user_id) == "ru"


def _reply_keyboard(labels: list[list[str]]) -> dict[str, Any]:
    return {
        "keyboard": [[{"text": label} for label in row] for row in labels],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def _inline_keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


def _main_menu_markup(ru: bool) -> dict[str, Any]:
    if ru:
        return _reply_keyboard(
            [
                ["📌 Статус кейса", "🏠 Кабинет"],
                ["❓ Помощь", "🔕 Отключить"],
            ]
        )
    return _reply_keyboard(
        [
            ["📌 Case status", "🏠 Portal"],
            ["❓ Help", "🔕 Disconnect"],
        ]
    )


def _guest_menu_markup(ru: bool) -> dict[str, Any]:
    if ru:
        return _reply_keyboard([["🔗 Как подключить", "❓ Помощь"]])
    return _reply_keyboard([["🔗 How to connect", "❓ Help"]])


def _welcome_guest_text(ru: bool) -> str:
    if ru:
        return (
            "👋 Добро пожаловать в Spainza!\n\n"
            "Этот чат — ваш канал важных уведомлений, чтобы вы ничего не пропустили по делу в Испании.\n\n"
            "Сюда будут приходить:\n"
            "• новые сообщения от менеджера\n"
            "• запросы и статусы документов\n"
            "• изменения по вашему кейсу\n\n"
            "Чтобы подключить уведомления, откройте профиль в личном кабинете "
            "и нажмите «Открыть в Telegram»."
        )
    return (
        "👋 Welcome to Spainza!\n\n"
        "This chat is your channel for important updates, so you never miss what matters for your case in Spain.\n\n"
        "You will receive alerts about:\n"
        "• new messages from your manager\n"
        "• document requests and decisions\n"
        "• changes to your case status\n\n"
        "To enable notifications, open your profile in the portal "
        "and tap «Open in Telegram»."
    )


def _welcome_linked_text(ru: bool, *, name: str = "") -> str:
    greeting = f", {name}" if name else ""
    if ru:
        return (
            f"✅ Telegram подключён{greeting}!\n\n"
            "Теперь важные события по вашему кейсу будут приходить сюда — "
            "чтобы вы не пропустили ни сообщение менеджера, ни запрос документов, ни смену статуса.\n\n"
            "Проверить текущий статус или перейти в кабинет можно кнопками меню внизу."
        )
    return (
        f"✅ Telegram linked{greeting}!\n\n"
        "Important updates about your case will arrive here — "
        "so you won't miss a manager message, document request, or status change.\n\n"
        "Use the menu buttons below to check your case status or open the portal."
    )


def _welcome_returning_text(ru: bool) -> str:
    if ru:
        return (
            "👋 С возвращением!\n\n"
            "Ваш аккаунт подключён — важные уведомления Spainza приходят в этот чат.\n"
            "Выберите действие в меню ниже."
        )
    return (
        "👋 Welcome back!\n\n"
        "Your account is linked — important Spainza alerts are delivered to this chat.\n"
        "Choose an action in the menu below."
    )


def _profile_inline_markup(ru: bool) -> dict[str, Any]:
    return _inline_keyboard(
        [
            [
                {
                    "text": "👤 " + ("Открыть профиль" if ru else "Open profile"),
                    "url": lk_url("/frontend/lk/profile.html"),
                }
            ]
        ]
    )


def _status_inline_markup(ru: bool) -> dict[str, Any]:
    return _inline_keyboard(
        [
            [
                {
                    "text": "🏠 " + ("Кабинет" if ru else "Dashboard"),
                    "url": lk_url("/frontend/lk/dashboard.html"),
                }
            ],
            [
                {
                    "text": "📁 " + ("Документы" if ru else "Documents"),
                    "url": lk_url("/frontend/lk/documents.html"),
                },
                {
                    "text": "📋 " + ("Кейс" if ru else "Case"),
                    "url": lk_url("/frontend/lk/case.html"),
                },
            ],
        ]
    )


def _unlink_confirm_markup(ru: bool) -> dict[str, Any]:
    return _inline_keyboard(
        [
            [
                {
                    "text": "✅ " + ("Да, отключить" if ru else "Yes, disconnect"),
                    "callback_data": CB_UNLINK_YES,
                },
                {
                    "text": "❌ " + ("Отмена" if ru else "Cancel"),
                    "callback_data": CB_UNLINK_NO,
                },
            ]
        ]
    )


def _send(
    connection: sqlite3.Connection,
    chat_id: int,
    text: str,
    *,
    reply_markup: Optional[dict[str, Any]] = None,
) -> None:
    token = Config.TELEGRAM_BOT_TOKEN
    if not token:
        return
    send_message(token, chat_id, text, reply_markup=reply_markup)


def handle_update(connection: sqlite3.Connection, update: dict, *, bot_username: str = "") -> None:
    callback = update.get("callback_query")
    if callback:
        _handle_callback(connection, callback, bot_username=bot_username)
        return

    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    chat_id = int(chat_id)

    from_user = message.get("from") or {}
    telegram_user_id = from_user.get("id")
    telegram_username = from_user.get("username")
    text = str(message.get("text") or "").strip()

    if not text:
        return

    lowered = text.lower()
    if lowered.startswith("/start"):
        _handle_start(
            connection,
            chat_id,
            text,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            from_user=from_user,
            bot_username=bot_username,
        )
        return

    if lowered.startswith("/status"):
        _handle_status(connection, chat_id)
        return

    if lowered.startswith("/unlink"):
        _handle_unlink_prompt(connection, chat_id)
        return

    if lowered.startswith("/help"):
        _handle_help(connection, chat_id, bot_username=bot_username)
        return

    menu_action = MENU_TEXT_ACTIONS.get(text)
    if menu_action:
        _dispatch_menu_action(connection, chat_id, menu_action, bot_username=bot_username)
        return


def _dispatch_menu_action(
    connection: sqlite3.Connection,
    chat_id: int,
    action: str,
    *,
    bot_username: str,
) -> None:
    if action == "status":
        _handle_status(connection, chat_id)
    elif action == "portal":
        _handle_portal(connection, chat_id)
    elif action == "help":
        _handle_help(connection, chat_id, bot_username=bot_username)
    elif action == "unlink":
        _handle_unlink_prompt(connection, chat_id)
    elif action == "connect":
        _handle_connect_hint(connection, chat_id)


def _handle_callback(
    connection: sqlite3.Connection,
    callback: dict,
    *,
    bot_username: str,
) -> None:
    callback_id = str(callback.get("id") or "")
    data = str(callback.get("data") or "")
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return
    chat_id = int(chat_id)

    token = Config.TELEGRAM_BOT_TOKEN
    if token and callback_id:
        try:
            answer_callback_query(token, callback_id)
        except Exception:
            pass

    if data == CB_STATUS:
        _handle_status(connection, chat_id)
    elif data == CB_HELP:
        _handle_help(connection, chat_id, bot_username=bot_username)
    elif data == CB_UNLINK:
        _handle_unlink_prompt(connection, chat_id)
    elif data == CB_UNLINK_YES:
        _handle_unlink_confirm(connection, chat_id)
    elif data == CB_UNLINK_NO:
        ru = _is_ru_for_chat(connection, chat_id)
        linked = _linked_user_id_for_chat(connection, chat_id) is not None
        _send(
            connection,
            chat_id,
            "Отменено." if ru else "Cancelled.",
            reply_markup=_main_menu_markup(ru) if linked else _guest_menu_markup(ru),
        )
    elif data == CB_CONNECT:
        _handle_connect_hint(connection, chat_id)


def _handle_login_start(
    connection: sqlite3.Connection,
    chat_id: int,
    start_code: str,
    *,
    telegram_user_id: Optional[int],
    telegram_username: Optional[str],
    from_user: dict,
) -> None:
    session = consume_telegram_login_session(
        connection,
        start_code,
        Config.SECRET_KEY,
    )
    ru = _is_ru_for_chat(connection, chat_id)
    if not session or telegram_user_id is None:
        _send(
            connection,
            chat_id,
            (
                "❌ Сессия входа недействительна или истекла. Вернитесь на spainza.com и попробуйте снова."
                if ru
                else "❌ Login session is invalid or expired. Go back to spainza.com and try again."
            ),
        )
        return

    payload = {
        "id": telegram_user_id,
        "first_name": from_user.get("first_name"),
        "last_name": from_user.get("last_name"),
        "username": telegram_username or from_user.get("username"),
        "photo_url": from_user.get("photo_url"),
        "auth_date": int(time.time()),
    }
    user_id, _created, error_code = resolve_or_create_user_from_telegram(connection, payload)
    if not user_id:
        _send(
            connection,
            chat_id,
            (
                "❌ Не удалось выполнить вход. Попробуйте снова на сайте."
                if ru
                else "❌ Could not sign you in. Please try again on the website."
            ),
        )
        return

    complete_telegram_login_session(connection, int(session["id"]), user_id)
    upsert_telegram_link(
        connection,
        user_id,
        chat_id,
        telegram_user_id=int(telegram_user_id),
        telegram_username=telegram_username,
    )
    _send(
        connection,
        chat_id,
        (
            "✅ Вход подтверждён!\n\nВернитесь в браузер — вход завершится автоматически."
            if ru
            else "✅ Sign-in confirmed!\n\nReturn to your browser to finish logging in."
        ),
        reply_markup=_main_menu_markup(ru),
    )


def _handle_start(
    connection: sqlite3.Connection,
    chat_id: int,
    text: str,
    *,
    telegram_user_id: Optional[int],
    telegram_username: Optional[str],
    from_user: dict,
    bot_username: str,
) -> None:
    login_match = LOGIN_START_CODE_RE.match(text)
    if login_match:
        _handle_login_start(
            connection,
            chat_id,
            login_match.group(1),
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            from_user=from_user,
        )
        return

    match = START_CODE_RE.match(text)
    code = (match.group(1) if match else None) or ""

    if code:
        user_id = consume_telegram_link_code(connection, code, Config.SECRET_KEY)
        if not user_id:
            ru = _is_ru_for_chat(connection, chat_id)
            _send(
                connection,
                chat_id,
                (
                    "❌ Код недействителен или истёк.\n\n"
                    "Откройте профиль на spainza.com → «Открыть в Telegram» и получите новый код."
                    if ru
                    else "❌ Code is invalid or expired.\n\n"
                    "Open your profile at spainza.com → «Open in Telegram» for a new code."
                ),
                reply_markup=_profile_inline_markup(ru),
            )
            return
        upsert_telegram_link(
            connection,
            user_id,
            chat_id,
            telegram_user_id=int(telegram_user_id) if telegram_user_id else None,
            telegram_username=telegram_username,
        )
        ru = _locale_for_user(connection, user_id) == "ru"
        user = get_user_by_id(connection, user_id)
        name = (user["name"] or user["email"] or "").strip() if user else ""
        _send(
            connection,
            chat_id,
            _welcome_linked_text(ru, name=name),
            reply_markup=_main_menu_markup(ru),
        )
        return

    ru = _is_ru_for_chat(connection, chat_id)
    linked = _linked_user_id_for_chat(connection, chat_id) is not None
    if linked:
        _send(
            connection,
            chat_id,
            _welcome_returning_text(ru),
            reply_markup=_main_menu_markup(ru),
        )
        return

    _send(
        connection,
        chat_id,
        _welcome_guest_text(ru),
        reply_markup=_guest_menu_markup(ru),
    )
    _send(
        connection,
        chat_id,
        "👇 " + ("Быстрый переход:" if ru else "Quick link:"),
        reply_markup=_profile_inline_markup(ru),
    )


def _handle_connect_hint(connection: sqlite3.Connection, chat_id: int) -> None:
    ru = _is_ru_for_chat(connection, chat_id)
    _send(
        connection,
        chat_id,
        (
            "🔗 Как подключить\n\n"
            "1. Войдите в личный кабинет Spainza\n"
            "2. Откройте профиль\n"
            "3. Нажмите «Открыть в Telegram»\n"
            "4. Подтвердите привязку в этом чате"
            if ru
            else "🔗 How to connect\n\n"
            "1. Sign in to Spainza portal\n"
            "2. Open your profile\n"
            "3. Tap «Open in Telegram»\n"
            "4. Confirm linking in this chat"
        ),
        reply_markup=_profile_inline_markup(ru),
    )


def _handle_portal(connection: sqlite3.Connection, chat_id: int) -> None:
    ru = _is_ru_for_chat(connection, chat_id)
    if not _linked_user_id_for_chat(connection, chat_id):
        _handle_connect_hint(connection, chat_id)
        return
    _send(
        connection,
        chat_id,
        "🏠 " + ("Откройте личный кабинет:" if ru else "Open your portal:"),
        reply_markup=_status_inline_markup(ru),
    )


def _active_timeline_step(case_data: Optional[dict]) -> str:
    if not case_data or not isinstance(case_data.get("timeline"), list):
        return "—"
    for step in case_data["timeline"]:
        if isinstance(step, dict) and str(step.get("status") or "").lower() == "active":
            return str(step.get("title") or "—").strip() or "—"
    return "—"


def _handle_status(connection: sqlite3.Connection, chat_id: int) -> None:
    user_id = _linked_user_id_for_chat(connection, chat_id)
    if not user_id:
        ru = _is_ru_for_chat(connection, chat_id)
        _send(
            connection,
            chat_id,
            (
                "Сначала подключите аккаунт через профиль Spainza."
                if ru
                else "Link your account first via the Spainza profile."
            ),
            reply_markup=_guest_menu_markup(ru),
        )
        _send(
            connection,
            chat_id,
            "👇 " + ("Перейти в профиль:" if ru else "Go to profile:"),
            reply_markup=_profile_inline_markup(ru),
        )
        return

    user = get_user_by_id(connection, user_id)
    if not user:
        _send(connection, chat_id, "Аккаунт не найден.")
        return

    locale = _locale_for_user(connection, user_id)
    ru = locale == "ru"
    case_data = get_case_data_by_user_id(connection, user_id)
    pending_requests = count_sent_document_requests(case_data)
    active_step = _active_timeline_step(case_data)

    text = (
        f"📌 {'Статус кейса' if ru else 'Case status'}\n\n"
        f"{'Этап' if ru else 'Stage'}: {active_step}\n"
        f"{'Ожидают загрузки' if ru else 'Pending uploads'}: {pending_requests}"
    )
    _send(connection, chat_id, text, reply_markup=_status_inline_markup(ru))


def _handle_unlink_prompt(connection: sqlite3.Connection, chat_id: int) -> None:
    if not _linked_user_id_for_chat(connection, chat_id):
        ru = _is_ru_for_chat(connection, chat_id)
        _send(
            connection,
            chat_id,
            "Аккаунт не подключён." if ru else "Account is not linked.",
            reply_markup=_guest_menu_markup(ru),
        )
        return

    ru = _is_ru_for_chat(connection, chat_id)
    _send(
        connection,
        chat_id,
        (
            "🔕 Отключить уведомления?\n\n"
            "Вы перестанете получать сообщения от Spainza в Telegram."
            if ru
            else "🔕 Disconnect notifications?\n\n"
            "You will stop receiving Spainza alerts in Telegram."
        ),
        reply_markup=_unlink_confirm_markup(ru),
    )


def _handle_unlink_confirm(connection: sqlite3.Connection, chat_id: int) -> None:
    user_id = _linked_user_id_for_chat(connection, chat_id)
    if not user_id:
        ru = _is_ru_for_chat(connection, chat_id)
        _send(
            connection,
            chat_id,
            "Аккаунт не подключён." if ru else "Account is not linked.",
            reply_markup=_guest_menu_markup(ru),
        )
        return

    ru = _locale_for_user(connection, user_id) == "ru"
    deactivate_telegram_link(connection, user_id)
    _send(
        connection,
        chat_id,
        (
            "Telegram-уведомления отключены.\n"
            "Подключить снова можно через профиль в личном кабинете."
            if ru
            else "Telegram notifications are off.\n"
            "You can link again from your portal profile."
        ),
        reply_markup=_guest_menu_markup(ru),
    )
    _send(
        connection,
        chat_id,
        "👇 " + ("Профиль:" if ru else "Profile:"),
        reply_markup=_profile_inline_markup(ru),
    )


def _handle_help(
    connection: sqlite3.Connection,
    chat_id: int,
    *,
    bot_username: str,
) -> None:
    user_id = _linked_user_id_for_chat(connection, chat_id)
    ru = _locale_for_user(connection, user_id) == "ru" if user_id else True
    linked = user_id is not None

    text = (
        "ℹ️ Spainza Bot\n\n"
        "Используйте кнопки меню внизу экрана:\n"
        "• 📌 Статус кейса — активный этап и документы\n"
        "• 🏠 Кабинет — быстрые ссылки в ЛК\n"
        "• 🔕 Отключить — отвязать Telegram\n\n"
        "Подключение: профиль → «Открыть в Telegram»."
        if ru
        else "ℹ️ Spainza Bot\n\n"
        "Use the menu buttons at the bottom:\n"
        "• 📌 Case status — active stage and documents\n"
        "• 🏠 Portal — quick links to the portal\n"
        "• 🔕 Disconnect — unlink Telegram\n\n"
        "To connect: profile → «Open in Telegram»."
    )
    _send(
        connection,
        chat_id,
        text,
        reply_markup=_main_menu_markup(ru) if linked else _guest_menu_markup(ru),
    )
