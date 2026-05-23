"""Security helpers for passwords and auth tokens."""

import re
import time

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


def is_valid_email(email: str) -> bool:
    """Validate email format using regex."""
    return bool(EMAIL_REGEX.fullmatch(email or ""))


def is_valid_password(password: str) -> bool:
    """Validate minimum password strength."""
    if len(password or "") < 8:
        return False
    if not re.search(r"[a-z]", password):
        return False
    if not re.search(r"[A-Z]", password):
        return False
    return True


def hash_password(password: str) -> str:
    """Return a secure hash for a plain password."""
    return generate_password_hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Validate a plain password against stored hash."""
    return check_password_hash(password_hash, password)


def generate_auth_token(secret_key: str, user_id: int) -> str:
    """Generate signed auth token for user."""
    serializer = URLSafeTimedSerializer(secret_key=secret_key, salt="auth-token")
    return serializer.dumps({"user_id": user_id, "issued_at": int(time.time())})


def verify_auth_token(secret_key: str, token: str, max_age_seconds: int = 86400):
    """Validate signed auth token and return payload or None."""
    serializer = URLSafeTimedSerializer(secret_key=secret_key, salt="auth-token")
    try:
        return serializer.loads(token, max_age=max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
