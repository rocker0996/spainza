"""Minimal Telegram Bot API client (stdlib only)."""

from __future__ import annotations

import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Optional

_opener: urllib.request.OpenerDirector | None = None


_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    infos = _orig_getaddrinfo(host, port, family, type, proto, flags)
    ipv4 = [info for info in infos if info[0] == socket.AF_INET]
    return ipv4 or infos


def _build_opener() -> urllib.request.OpenerDirector:
    global _opener
    if _opener is not None:
        return _opener

    handlers: list[urllib.request.BaseHandler] = []
    proxy = os.environ.get("TELEGRAM_HTTPS_PROXY", "").strip()
    if proxy:
        handlers.append(
            urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        )
    handlers.append(urllib.request.HTTPSHandler())
    _opener = urllib.request.build_opener(*handlers)
    return _opener


socket.getaddrinfo = _ipv4_getaddrinfo  # type: ignore[assignment]


class TelegramApiError(RuntimeError):
    def __init__(self, message: str, *, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


def _api_request(
    token: str,
    method: str,
    payload: Optional[dict[str, Any]] = None,
    *,
    timeout: float = 35.0,
) -> dict[str, Any]:
    if not token:
        raise TelegramApiError("TELEGRAM_BOT_TOKEN is not configured")

    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with _build_opener().open(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise TelegramApiError(raw or str(exc), status_code=exc.code) from exc
    except urllib.error.URLError as exc:
        raise TelegramApiError(str(exc)) from exc

    if not body.get("ok"):
        description = str(body.get("description") or "Telegram API error")
        raise TelegramApiError(description)
    return body


_cached_bot_username: str | None = None


def _bot_username_fallback() -> str | None:
    raw = os.environ.get("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
    return raw or None


def get_bot_username(token: str) -> str | None:
    global _cached_bot_username
    if _cached_bot_username:
        return _cached_bot_username
    if not token:
        return _bot_username_fallback()
    try:
        me = get_me(token)
        _cached_bot_username = str(me.get("username") or "").strip() or None
    except TelegramApiError:
        _cached_bot_username = _bot_username_fallback()
    return _cached_bot_username


def get_me(token: str) -> dict[str, Any]:
    return _api_request(token, "getMe")["result"]


def send_message(
    token: str,
    chat_id: int,
    text: str,
    *,
    reply_markup: Optional[dict[str, Any]] = None,
    disable_web_page_preview: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": disable_web_page_preview,
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return _api_request(token, "sendMessage", payload)["result"]


def answer_callback_query(
    token: str,
    callback_query_id: str,
    *,
    text: Optional[str] = None,
    show_alert: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text
    if show_alert:
        payload["show_alert"] = True
    return _api_request(token, "answerCallbackQuery", payload)["result"]


def set_my_commands(
    token: str,
    commands: list[dict[str, str]],
    *,
    language_code: Optional[str] = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"commands": commands}
    if language_code:
        payload["language_code"] = language_code
    return _api_request(token, "setMyCommands", payload)["result"]


def delete_webhook(token: str) -> None:
    _api_request(token, "deleteWebhook", {"drop_pending_updates": False})


def get_updates(
    token: str,
    *,
    offset: Optional[int] = None,
    timeout: int = 25,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {"timeout": timeout}
    if offset is not None:
        payload["offset"] = offset
    return _api_request(token, "getUpdates", payload, timeout=timeout + 10)["result"]
