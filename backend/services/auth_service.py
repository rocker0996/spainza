"""Authentication business logic for account activation and password recovery."""

from __future__ import annotations

from datetime import timedelta
from email.message import EmailMessage
import hashlib
import secrets
import smtplib
from typing import Any
from urllib.parse import urlencode

from flask import current_app

from models.user import (
    apply_pending_email_change,
    get_user_by_email,
    get_user_by_email_verification_token_hash,
    get_user_by_id,
    get_user_by_password_reset_token_hash,
    get_user_by_pending_email_token_hash,
    mark_user_email_verified,
    set_email_verification_token,
    set_password_reset_token,
    set_pending_email_change,
    update_user_password_and_clear_reset,
)
from services.email_templates import (
    email_change_confirmation_bodies,
    email_changed_notification_bodies,
    password_reset_email_bodies,
    verification_email_bodies,
)
from utils.security import hash_password
from utils.time import parse_storage_datetime, to_storage_datetime, utc_now


def generate_plain_token() -> str:
    """Generate a URL-safe one-time token."""
    return secrets.token_urlsafe(32)


def hash_one_time_token(token: str) -> str:
    """Hash a one-time token before storing it."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def is_email_verification_pending(user: Any) -> bool:
    """
    Existing users without verification columns are treated as legacy-verified.
    Newly registered users have a pending token until they verify email.
    """
    if not user:
        return False
    return bool(user["email_verification_token_hash"] and not user["email_verified_at"])


def issue_email_verification_token(connection, user_id: int) -> tuple[str, str]:
    """Create and persist a verification token, returning token and expiry."""
    token = generate_plain_token()
    now = utc_now()
    expires_at = now + timedelta(
        seconds=int(current_app.config.get("EMAIL_VERIFICATION_TTL_SECONDS", 172800))
    )
    expires_at_text = to_storage_datetime(expires_at)
    set_email_verification_token(
        connection,
        user_id,
        hash_one_time_token(token),
        expires_at_text,
        to_storage_datetime(now),
    )
    return token, expires_at_text


def verify_email_token(connection, token: str) -> tuple[bool, str, int | None]:
    """Verify a one-time email token and activate the account."""
    token_hash = hash_one_time_token(token)
    user = get_user_by_email_verification_token_hash(connection, token_hash)
    if not user:
        return False, "invalid_token", None
    if user["email_verified_at"]:
        return True, "already_verified", int(user["id"])

    expires_at = parse_storage_datetime(user["email_verification_expires_at"])
    if not expires_at or expires_at < utc_now():
        return False, "expired_token", int(user["id"])

    mark_user_email_verified(connection, int(user["id"]), to_storage_datetime(utc_now()))
    return True, "verified", int(user["id"])


def issue_password_reset_token(connection, user_id: int) -> tuple[str, str]:
    """Create and persist a password reset token, returning token and expiry."""
    token = generate_plain_token()
    now = utc_now()
    expires_at = now + timedelta(
        seconds=int(current_app.config.get("PASSWORD_RESET_TTL_SECONDS", 3600))
    )
    expires_at_text = to_storage_datetime(expires_at)
    set_password_reset_token(
        connection,
        user_id,
        hash_one_time_token(token),
        expires_at_text,
        to_storage_datetime(now),
    )
    return token, expires_at_text


def reset_password_with_token(connection, token: str, new_password: str) -> tuple[bool, str, int | None]:
    """Validate a reset token, set a new password, and revoke old auth tokens."""
    token_hash = hash_one_time_token(token)
    user = get_user_by_password_reset_token_hash(connection, token_hash)
    if not user:
        return False, "invalid_token", None

    expires_at = parse_storage_datetime(user["password_reset_expires_at"])
    if not expires_at or expires_at < utc_now():
        return False, "expired_token", int(user["id"])

    now_text = to_storage_datetime(utc_now())
    update_user_password_and_clear_reset(
        connection,
        int(user["id"]),
        hash_password(new_password),
        now_text,
    )
    return True, "password_reset", int(user["id"])


def build_public_url(path: str, token: str) -> str:
    """Build a public account-action URL."""
    base_url = str(current_app.config.get("PUBLIC_BASE_URL") or "").rstrip("/")
    if not base_url:
        base_url = (current_app.config.get("SERVER_NAME") or "").rstrip("/")
    if not base_url:
        base_url = ""

    separator = "&" if "?" in path else "?"
    return f"{base_url}{path}{separator}{urlencode({'token': token})}"


def send_account_email(
    to_email: str,
    subject: str,
    text_body: str,
    *,
    html_body: str | None = None,
) -> dict[str, Any]:
    """
    Send an account email when SMTP is configured.
    Without SMTP settings, log the body so the flow can be tested locally.
    """
    host = current_app.config.get("SMTP_HOST")
    sender = current_app.config.get("SMTP_FROM_EMAIL") or current_app.config.get("SMTP_USERNAME")
    if not host or not sender:
        current_app.logger.info("SMTP not configured; account email to %s:\n%s", to_email, text_body)
        return {"sent": False, "reason": "smtp_not_configured"}

    message = EmailMessage()
    message["From"] = sender
    message["To"] = to_email
    message["Subject"] = subject
    message.set_content(text_body)
    if html_body:
        message.add_alternative(html_body, subtype="html")

    port = int(current_app.config.get("SMTP_PORT", 587))
    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    use_ssl = bool(current_app.config.get("SMTP_USE_SSL", False))
    use_tls = bool(current_app.config.get("SMTP_USE_TLS", True))

    if use_ssl:
        smtp_factory = lambda: smtplib.SMTP_SSL(host, port, timeout=15)
    else:
        smtp_factory = lambda: smtplib.SMTP(host, port, timeout=15)

    with smtp_factory() as smtp:
        if not use_ssl and use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)

    return {"sent": True}


def send_verification_email(to_email: str, token: str) -> dict[str, Any]:
    """Send email verification instructions."""
    url = build_public_url("/api/verify-email", token)
    text_body, html_body = verification_email_bodies(url)
    return send_account_email(
        to_email,
        "Подтвердите email в Spainza",
        text_body,
        html_body=html_body,
    )


def send_password_reset_email(to_email: str, token: str) -> dict[str, Any]:
    """Send password reset instructions."""
    url = build_public_url("/frontend/login.html", token)
    text_body, html_body = password_reset_email_bodies(url)
    return send_account_email(
        to_email,
        "Восстановление пароля Spainza",
        text_body,
        html_body=html_body,
    )


TELEGRAM_SYNTHETIC_EMAIL_SUFFIX = "@telegram.users.spainza"


def is_telegram_synthetic_email(email: str | None) -> bool:
    """True for placeholder emails assigned to Telegram-only accounts."""
    return str(email or "").strip().lower().endswith(TELEGRAM_SYNTHETIC_EMAIL_SUFFIX)


def issue_pending_email_change_token(
    connection, user_id: int, pending_email: str
) -> tuple[str, str]:
    """Create and persist a pending-email confirmation token."""
    token = generate_plain_token()
    now = utc_now()
    expires_at = now + timedelta(
        seconds=int(current_app.config.get("EMAIL_CHANGE_TTL_SECONDS", 172800))
    )
    expires_at_text = to_storage_datetime(expires_at)
    set_pending_email_change(
        connection,
        user_id,
        pending_email.strip().lower(),
        hash_one_time_token(token),
        expires_at_text,
        to_storage_datetime(now),
    )
    return token, expires_at_text


def request_email_change(connection, user_id: int, new_email: str) -> tuple[bool, str, dict[str, Any]]:
    """Start an email change: confirmation is sent to the new address."""
    user = get_user_by_id(connection, user_id)
    if not user:
        return False, "user_not_found", {}

    current_email = str(user["email"] or "").strip().lower()
    normalized_new = str(new_email or "").strip().lower()
    if not normalized_new:
        return False, "invalid_email", {}
    if normalized_new == current_email:
        return True, "unchanged", {}

    if is_telegram_synthetic_email(current_email):
        return False, "telegram_account", {}

    existing = get_user_by_email(connection, normalized_new)
    if existing and int(existing["id"]) != int(user_id):
        return False, "email_taken", {}

    token, expires_at = issue_pending_email_change_token(connection, user_id, normalized_new)
    delivery = send_email_change_confirmation_email(normalized_new, token)
    return True, "pending", {
        "pending_email": normalized_new,
        "expires_at": expires_at,
        "email_delivery": delivery,
    }


def confirm_pending_email_change(
    connection, token: str
) -> tuple[bool, str, int | None, str | None, str | None]:
    """
    Confirm a pending email change.
    Returns ok, code, user_id, old_email, new_email.
    """
    token_hash = hash_one_time_token(token)
    user = get_user_by_pending_email_token_hash(connection, token_hash)
    if not user:
        return False, "invalid_token", None, None, None

    new_email = str(user["pending_email"] or "").strip().lower()
    if not new_email:
        return False, "invalid_token", None, None, None

    expires_at = parse_storage_datetime(user["pending_email_expires_at"])
    if not expires_at or expires_at < utc_now():
        return False, "expired_token", int(user["id"]), None, None

    existing = get_user_by_email(connection, new_email)
    if existing and int(existing["id"]) != int(user["id"]):
        return False, "email_taken", int(user["id"]), None, None

    old_email = str(user["email"] or "").strip().lower()
    apply_pending_email_change(connection, int(user["id"]), new_email)
    send_email_changed_notification_email(old_email)
    return True, "confirmed", int(user["id"]), old_email, new_email


def send_email_change_confirmation_email(to_email: str, token: str) -> dict[str, Any]:
    """Send confirmation instructions to the new email address."""
    url = build_public_url("/api/verify-email-change", token)
    text_body, html_body = email_change_confirmation_bodies(url)
    return send_account_email(
        to_email,
        "Подтвердите новый email в Spainza",
        text_body,
        html_body=html_body,
    )


def send_email_changed_notification_email(to_email: str) -> dict[str, Any]:
    """Notify the previous email that the account address was changed."""
    text_body, html_body = email_changed_notification_bodies()
    return send_account_email(
        to_email,
        "Email аккаунта Spainza изменён",
        text_body,
        html_body=html_body,
    )

