"""Application configuration."""

import os


def _parse_csv_env(name: str) -> tuple[str, ...]:
    raw = os.getenv(name, "")
    if not raw:
        return tuple()
    return tuple(item.strip().rstrip("/") for item in raw.split(",") if item.strip())


def _parse_int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return int(default)
    try:
        return int(raw)
    except ValueError:
        return int(default)


def _parse_bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    if not raw:
        return default
    return raw not in {"0", "false", "no", "off"}


def is_production_env() -> bool:
    candidates = (
        os.getenv("APP_ENV", ""),
        os.getenv("FLASK_ENV", ""),
        os.getenv("ENV", ""),
    )
    return any(value.strip().lower() == "production" for value in candidates if value)


def _is_production_env() -> bool:
    return is_production_env()


def _load_debug_flag() -> bool:
    if is_production_env():
        if _parse_bool_env("FLASK_DEBUG", False):
            raise RuntimeError("FLASK_DEBUG must not be enabled in production")
        return False
    return _parse_bool_env("FLASK_DEBUG", default=False)


def _load_secret_key() -> str:
    secret_key = os.getenv("SECRET_KEY", "").strip()
    is_production = _is_production_env()
    if not secret_key:
        if is_production:
            raise RuntimeError("SECRET_KEY must be set in production environment")
        return "dev-secret-key"

    if is_production:
        weak_values = {"dev-secret-key", "changeme", "secret", "password"}
        if secret_key.lower() in weak_values:
            raise RuntimeError("SECRET_KEY is too weak for production environment")
        if len(secret_key) < 32:
            raise RuntimeError("SECRET_KEY must be at least 32 characters in production")

    return secret_key


class Config:
    """Runtime configuration loaded from environment variables."""

    SECRET_KEY = _load_secret_key()
    DEBUG = _load_debug_flag()
    FLASK_RUN_HOST = os.getenv("FLASK_RUN_HOST", "127.0.0.1").strip() or "127.0.0.1"
    FLASK_RUN_PORT = _parse_int_env("FLASK_RUN_PORT", 5000)
    FLASK_USE_RELOADER = _parse_bool_env("FLASK_USE_RELOADER", default=True)
    """Аккаунт поддержки в ЛК (числовой id в БД). Для чата по умолчанию используется его публичный display_id из профиля."""
    PORTAL_SUPPORT_USER_ID = int(os.getenv("PORTAL_SUPPORT_USER_ID", "11"))
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "")

    EMAIL_VERIFICATION_TTL_SECONDS = int(os.getenv("EMAIL_VERIFICATION_TTL_SECONDS", "172800"))
    PASSWORD_RESET_TTL_SECONDS = int(os.getenv("PASSWORD_RESET_TTL_SECONDS", "3600"))

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", SMTP_USERNAME)
    SMTP_USE_TLS = os.getenv("SMTP_USE_TLS", "1").strip().lower() not in {"0", "false", "no"}
    CORS_ALLOWED_ORIGINS = _parse_csv_env("CORS_ALLOWED_ORIGINS")
    RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "1").strip().lower() not in {"0", "false", "no"}
    AUTH_RATE_LIMIT_IP_MAX = _parse_int_env("AUTH_RATE_LIMIT_IP_MAX", 12)
    AUTH_RATE_LIMIT_IP_WINDOW_SECONDS = _parse_int_env("AUTH_RATE_LIMIT_IP_WINDOW_SECONDS", 300)
    AUTH_RATE_LIMIT_EMAIL_MAX = _parse_int_env("AUTH_RATE_LIMIT_EMAIL_MAX", 6)
    AUTH_RATE_LIMIT_EMAIL_WINDOW_SECONDS = _parse_int_env("AUTH_RATE_LIMIT_EMAIL_WINDOW_SECONDS", 900)
    UPLOAD_RATE_LIMIT_IP_MAX = _parse_int_env("UPLOAD_RATE_LIMIT_IP_MAX", 30)
    UPLOAD_RATE_LIMIT_IP_WINDOW_SECONDS = _parse_int_env("UPLOAD_RATE_LIMIT_IP_WINDOW_SECONDS", 600)
    UPLOAD_RATE_LIMIT_USER_MAX = _parse_int_env("UPLOAD_RATE_LIMIT_USER_MAX", 40)
    UPLOAD_RATE_LIMIT_USER_WINDOW_SECONDS = _parse_int_env("UPLOAD_RATE_LIMIT_USER_WINDOW_SECONDS", 600)
    MESSAGE_RATE_LIMIT_IP_MAX = _parse_int_env("MESSAGE_RATE_LIMIT_IP_MAX", 120)
    MESSAGE_RATE_LIMIT_IP_WINDOW_SECONDS = _parse_int_env("MESSAGE_RATE_LIMIT_IP_WINDOW_SECONDS", 60)
    MESSAGE_RATE_LIMIT_USER_MAX = _parse_int_env("MESSAGE_RATE_LIMIT_USER_MAX", 160)
    MESSAGE_RATE_LIMIT_USER_WINDOW_SECONDS = _parse_int_env("MESSAGE_RATE_LIMIT_USER_WINDOW_SECONDS", 60)

