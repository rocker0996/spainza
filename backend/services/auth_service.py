"""Authentication business logic for account activation and password recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
import hashlib
import secrets
import smtplib
from typing import Any
from urllib.parse import urlencode

from flask import current_app

from models.user import (
    get_user_by_email_verification_token_hash,
    get_user_by_password_reset_token_hash,
    mark_user_email_verified,
    set_email_verification_token,
    set_password_reset_token,
    update_user_password_and_clear_reset,
)
from utils.security import hash_password


def utc_now() -> datetime:
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def to_storage_datetime(value: datetime) -> str:
    """Serialize datetime for SQLite text columns."""
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_storage_datetime(value: str | None) -> datetime | None:
    """Parse SQLite text datetime from this service."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


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


def send_account_email(to_email: str, subject: str, text_body: str) -> dict[str, Any]:
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

    port = int(current_app.config.get("SMTP_PORT", 587))
    username = current_app.config.get("SMTP_USERNAME")
    password = current_app.config.get("SMTP_PASSWORD")
    use_tls = bool(current_app.config.get("SMTP_USE_TLS", True))

    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if use_tls:
            smtp.starttls()
        if username and password:
            smtp.login(username, password)
        smtp.send_message(message)

    return {"sent": True}


def send_verification_email(to_email: str, token: str) -> dict[str, Any]:
    """Send email verification instructions."""
    url = build_public_url("/api/verify-email", token)
    return send_account_email(
        to_email,
        "Подтвердите email в Spainza",
        (
            "Здравствуйте!\n\n"
            "Чтобы активировать аккаунт Spainza, откройте ссылку:\n"
            f"{url}\n\n"
            "Если вы не регистрировались, просто проигнорируйте это письмо."
        ),
    )


def send_password_reset_email(to_email: str, token: str) -> dict[str, Any]:
    """Send password reset instructions."""
    url = build_public_url("/frontend/login.html", token)
    return send_account_email(
        to_email,
        "Восстановление пароля Spainza",
        (
            "Здравствуйте!\n\n"
            "Для смены пароля откройте ссылку и задайте новый пароль:\n"
            f"{url}\n\n"
            "Если вы не запрашивали восстановление, просто проигнорируйте это письмо."
        ),
    )

