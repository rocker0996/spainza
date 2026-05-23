"""User model queries for SQLite."""

import re
import secrets
import sqlite3
import string
from typing import Any

_DISPLAY_ID_PATTERN = re.compile(r"^[A-Z]{2}\d{4}$")

DEFAULT_ROLE_KEY = "user"

ROLE_DEFINITIONS = {
    "management": {
        "level": "1",
        "name_ru": "Управление",
        "description_ru": "Полный доступ к системе. Может назначать админов и уровни ниже.",
        "visa_label_ru": "Управление",
        "visa_label_en": "Management",
        "permissions": (
            "full_access",
            "assign_admin_and_lower",
            "review_documents",
            "approve_documents",
            "communicate_with_clients",
            "respond_to_applications",
            "respond_to_messages",
            "upload_documents",
            "download_documents",
            "request_role_change",
            "view_all_users",
        ),
    },
    "admin": {
        "level": "2",
        "name_ru": "Админ",
        "description_ru": "Просмотр и одобрение документов, общение с клиентами, ответы по заявкам.",
        "visa_label_ru": "Админ",
        "visa_label_en": "Admin",
        "permissions": (
            "assign_moderator_and_lower",
            "review_documents",
            "approve_documents",
            "communicate_with_clients",
            "respond_to_applications",
            "respond_to_messages",
            "view_lower_users",
        ),
    },
    "moderator": {
        "level": "3",
        "name_ru": "Модератор",
        "description_ru": "Проверка клиентских документов и назначение ролей от менеджера и ниже.",
        "visa_label_ru": "Модератор",
        "visa_label_en": "Moderator",
        "permissions": (
            "assign_manager_and_lower",
            "review_documents",
            "respond_to_messages",
            "view_assignable_users",
        ),
    },
    "manager": {
        "level": "4",
        "name_ru": "Менеджер",
        "description_ru": "Закреплённые клиенты: кейс, документы, сообщения (как модератор, но только по своим клиентам).",
        "visa_label_ru": "Менеджер",
        "visa_label_en": "Manager",
        "permissions": (
            "assign_client_roles",
            "review_documents",
            "approve_documents",
            "upload_documents",
            "download_documents",
            "respond_to_messages",
            "view_assigned_clients",
        ),
    },
    "client": {
        "level": "5",
        "name_ru": "Клиент",
        "description_ru": "Клиент с доступом к визовым программам.",
        "visa_label_ru": "Клиент",
        "visa_label_en": "Client",
        "permissions": (
            "request_role_change",
            "upload_documents",
            "download_documents",
        ),
    },
    "digital_nomad": {
        "level": "5",
        "name_ru": "Digital Nomad",
        "description_ru": "Клиент программы Digital Nomad.",
        "visa_label_ru": "Цифровой кочевник",
        "visa_label_en": "Digital Nomad",
        "permissions": (
            "request_role_change",
            "upload_documents",
            "download_documents",
        ),
    },
    "golden_visa": {
        "level": "5",
        "name_ru": "Golden Visa",
        "description_ru": "Клиент программы Golden Visa.",
        "visa_label_ru": "Золотая виза",
        "visa_label_en": "Golden Visa",
        "permissions": (
            "request_role_change",
            "upload_documents",
            "download_documents",
        ),
    },
    "user": {
        "level": "6",
        "name_ru": "Пользователь",
        "description_ru": "Базовый доступ после регистрации.",
        "visa_label_ru": "Пользователь",
        "visa_label_en": "User",
        "permissions": ("request_role_change",),
    },
}

ASSIGNABLE_ROLE_KEYS_BY_ACTOR = {
    "management": ("admin", "moderator", "manager", "client", "digital_nomad", "golden_visa", "user"),
    "admin": ("moderator", "manager", "client", "digital_nomad", "golden_visa", "user"),
    "moderator": ("manager", "client", "digital_nomad", "golden_visa", "user"),
    "manager": ("client", "digital_nomad", "golden_visa", "user"),
    "client": (),
    "digital_nomad": (),
    "golden_visa": (),
    "user": (),
}

# Mapping: which roles can be assigned through "Visa Path" field (костыль для управления ролями)
# Management видит все роли ниже себя
# Admin видит все роли ниже себя (не видит management и admin)
# Moderator видит все роли ниже себя (не видит management, admin, moderator)
# Manager видит только клиентские роли (digital_nomad, golden_visa, user)
ASSIGNABLE_VISA_TYPES_BY_ROLE = {
    "management": ("admin", "moderator", "manager", "client", "digital_nomad", "golden_visa", "user"),
    "admin": ("moderator", "manager", "client", "digital_nomad", "golden_visa", "user"),
    "moderator": ("manager", "client", "digital_nomad", "golden_visa", "user"),
    "manager": ("client", "digital_nomad", "golden_visa", "user"),  # Менеджеры видят только клиентские роли
    "client": (),
    "digital_nomad": (),
    "golden_visa": (),
    "user": (),
}


def create_users_table(connection: sqlite3.Connection) -> None:
    """Create users table if it does not exist."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            avatar TEXT,
            role_key TEXT NOT NULL DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    ensure_users_columns(connection)
    connection.commit()


def get_user_by_email(connection: sqlite3.Connection, email: str):
    """Get user row by email."""
    cursor = connection.execute(
        """
        SELECT
            id,
            email,
            password_hash,
            email_verified_at,
            email_verification_token_hash,
            email_verification_expires_at,
            password_reset_token_hash,
            password_reset_expires_at,
            auth_token_revoked_at,
            display_id
        FROM users
        WHERE email = ?
        """,
        (email,),
    )
    return cursor.fetchone()


def get_user_by_id(connection: sqlite3.Connection, user_id: int):
    """Get user profile row by id."""
    cursor = connection.execute(
        """
        SELECT
            id,
            name,
            email,
            avatar,
            role_key,
            created_at,
            phone,
            main_goal,
            locale,
            notify_email,
            notify_sms,
            notify_whatsapp,
            application_type,
            current_stage,
            display_id
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )
    return cursor.fetchone()


def get_user_auth_by_id(connection: sqlite3.Connection, user_id: int):
    """Get user auth row by id."""
    cursor = connection.execute(
        """
        SELECT
            id,
            email,
            password_hash,
            email_verified_at,
            email_verification_token_hash,
            email_verification_expires_at,
            password_reset_token_hash,
            password_reset_expires_at,
            auth_token_revoked_at,
            display_id
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    )
    return cursor.fetchone()


def create_user(connection: sqlite3.Connection, email: str, password_hash: str) -> tuple[int, str]:
    """Insert a new user and return (internal id, public display_id)."""
    for _ in range(128):
        display_id = random_user_display_id()
        try:
            cursor = connection.execute(
                """
                INSERT INTO users (email, password_hash, role_key, display_id)
                VALUES (?, ?, ?, ?)
                """,
                (email, password_hash, DEFAULT_ROLE_KEY, display_id),
            )
            connection.commit()
            return cursor.lastrowid, display_id
        except sqlite3.IntegrityError:
            connection.rollback()
            if get_user_by_email(connection, email):
                raise
            continue
    raise RuntimeError("Could not allocate a unique display_id for new user")


def ensure_users_columns(connection: sqlite3.Connection) -> None:
    """Add missing profile columns for existing databases."""
    cursor = connection.execute("PRAGMA table_info(users)")
    existing_columns = {row["name"] for row in cursor.fetchall()}

    if "name" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN name TEXT")
    if "avatar" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN avatar TEXT")
    if "role_key" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN role_key TEXT NOT NULL DEFAULT 'user'"
        )
    if "phone" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN phone TEXT")
    if "main_goal" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN main_goal TEXT")
    if "locale" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN locale TEXT DEFAULT 'ru'")
    if "notify_email" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN notify_email INTEGER NOT NULL DEFAULT 1")
    if "notify_sms" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN notify_sms INTEGER NOT NULL DEFAULT 0")
    if "notify_whatsapp" not in existing_columns:
        connection.execute(
            "ALTER TABLE users ADD COLUMN notify_whatsapp INTEGER NOT NULL DEFAULT 1"
        )
    if "application_type" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN application_type TEXT DEFAULT 'vnj_investment'")
    if "current_stage" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN current_stage TEXT DEFAULT 'consultation'")
    if "manager_invite_token" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN manager_invite_token TEXT")
    if "email_verified_at" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")
    if "email_verification_token_hash" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN email_verification_token_hash TEXT")
    if "email_verification_expires_at" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN email_verification_expires_at TEXT")
    if "email_verification_sent_at" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN email_verification_sent_at TEXT")
    if "password_reset_token_hash" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN password_reset_token_hash TEXT")
    if "password_reset_expires_at" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN password_reset_expires_at TEXT")
    if "password_reset_requested_at" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN password_reset_requested_at TEXT")
    if "auth_token_revoked_at" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN auth_token_revoked_at TEXT")
    if "display_id" not in existing_columns:
        connection.execute("ALTER TABLE users ADD COLUMN display_id TEXT")

    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_display_id ON users(display_id)"
    )

    backfill_missing_user_display_ids(connection)


def random_user_display_id() -> str:
    """Two Latin letters (A–Z) and four digits, e.g. QK9021."""
    letters = "".join(secrets.choice(string.ascii_uppercase) for _ in range(2))
    digits = f"{secrets.randbelow(10000):04d}"
    return letters + digits


def backfill_missing_user_display_ids(connection: sqlite3.Connection) -> None:
    """Assign display_id to legacy rows (NULL / empty)."""
    cursor = connection.execute(
        """
        SELECT id FROM users
        WHERE display_id IS NULL OR trim(display_id) = ''
        """
    )
    ids = [int(row["id"]) for row in cursor.fetchall()]
    for uid in ids:
        for _ in range(160):
            candidate = random_user_display_id()
            try:
                connection.execute(
                    "UPDATE users SET display_id = ? WHERE id = ?",
                    (candidate, uid),
                )
                break
            except sqlite3.IntegrityError:
                continue
        else:
            raise RuntimeError(f"Could not allocate display_id for user id={uid}")


def normalize_public_display_id_value(raw: str) -> str | None:
    """Return AA1234 uppercase if valid, else None."""
    s = str(raw or "").strip().upper().replace(" ", "")
    if _DISPLAY_ID_PATTERN.fullmatch(s):
        return s
    return None


def get_internal_user_id_by_display_id(
    connection: sqlite3.Connection, display_id_normalized: str
) -> int | None:
    row = connection.execute(
        "SELECT id FROM users WHERE display_id = ?",
        (display_id_normalized,),
    ).fetchone()
    return int(row["id"]) if row else None


def may_initiate_chat_with_numeric_counterpart(
    connection: sqlite3.Connection,
    current_user_id: int,
    other_user_id: int,
    *,
    support_user_id: int,
) -> bool:
    """
    Разрешить user_id без display_id только для «системных» контактов:
    поддержка, персональный менеджер из кейса, закреплённый клиент менеджера.
    """
    if int(other_user_id) == int(support_user_id):
        return True
    row = connection.execute(
        "SELECT 1 FROM case_data WHERE user_id = ? AND manager_id = ?",
        (current_user_id, other_user_id),
    ).fetchone()
    if row:
        return True
    row = connection.execute(
        "SELECT 1 FROM manager_clients WHERE manager_id = ? AND client_id = ?",
        (current_user_id, other_user_id),
    ).fetchone()
    return bool(row)


def resolve_payload_client_user_id(
    connection: sqlite3.Connection, payload: dict
) -> tuple[int | None, str | None]:
    """
    Parse client identifier from JSON: numeric internal id or public display_id (AA1234).
    Returns (user_id, error_code) where error_code matches assign_client_by_id messages.
    """
    raw = payload.get("client_id")
    if raw is None:
        return None, "missing_client_id"
    text = str(raw).strip()
    if not text:
        return None, "missing_client_id"
    compact = text.upper().replace(" ", "")
    if _DISPLAY_ID_PATTERN.fullmatch(compact):
        row = connection.execute(
            "SELECT id FROM users WHERE display_id = ?",
            (compact,),
        ).fetchone()
        if not row:
            return None, "client_not_found"
        return int(row["id"]), None
    try:
        numeric = int(text, 10)
    except ValueError:
        return None, "invalid_ids"
    if numeric < 1:
        return None, "invalid_ids"
    return numeric, None


def normalize_role_key(role_key: str) -> str:
    """Return a known role key or fallback to default user role."""
    if role_key in ROLE_DEFINITIONS:
        return role_key
    return DEFAULT_ROLE_KEY


def get_role_definition(role_key: str) -> dict:
    """Return role metadata for the given key."""
    normalized_key = normalize_role_key(role_key)
    role_data = dict(ROLE_DEFINITIONS[normalized_key])
    role_data["key"] = normalized_key
    return role_data


def get_role_permissions(role_key: str) -> list[str]:
    """Return permissions for the given role."""
    role_data = get_role_definition(role_key)
    return list(role_data["permissions"])


def is_portal_staff_role(role_key: str) -> bool:
    """Персонал ЛК: числовой уровень роли 1–4 (management … manager)."""
    try:
        level = float(get_role_definition(role_key)["level"])
    except (KeyError, TypeError, ValueError):
        return False
    return level <= 4.0


def get_assignable_roles(actor_role_key: str) -> list[dict]:
    """Return roles that can be assigned by a role holder."""
    normalized_actor = normalize_role_key(actor_role_key)
    assignable_keys = ASSIGNABLE_ROLE_KEYS_BY_ACTOR.get(normalized_actor, ())
    return [get_role_definition(role_key) for role_key in assignable_keys]


def can_assign_role(actor_role_key: str, target_role_key: str) -> bool:
    """Check if actor role can assign target role."""
    normalized_actor = normalize_role_key(actor_role_key)
    normalized_target = normalize_role_key(target_role_key)
    assignable_keys = ASSIGNABLE_ROLE_KEYS_BY_ACTOR.get(normalized_actor, ())
    return normalized_target in assignable_keys


def get_assignable_visa_types(actor_role_key: str) -> list[dict]:
    """Return roles that can be assigned through 'Visa Path' field (костыль).
    
    Returns a list of role objects with 'value' (role_key), 'label_ru', and 'label_en'.
    This is used to populate the "Визовый путь" dropdown which actually changes user roles.
    """
    normalized_actor = normalize_role_key(actor_role_key)
    assignable_role_keys = ASSIGNABLE_VISA_TYPES_BY_ROLE.get(normalized_actor, ())
    
    result = []
    for role_key in assignable_role_keys:
        if role_key in ROLE_DEFINITIONS:
            role_def = ROLE_DEFINITIONS[role_key]
            result.append({
                "value": role_key,
                "label_ru": role_def.get("visa_label_ru", role_def["name_ru"]),
                "label_en": role_def.get("visa_label_en", role_def["name_ru"])
            })
    
    return result


# Роли персонала: не показываем в «Шаблонах кейсов» (только клиентские визовые пути).
CASE_TEMPLATE_EXCLUDED_ROLE_KEYS = frozenset(
    {"management", "admin", "moderator", "manager"}
)

# Шаблон для роли «Пользователь» (ожидание) хранится у этого менеджера; в конфигураторе виден только ему.
GLOBAL_USER_ROLE_TEMPLATE_OWNER_ID = 1


def get_assignable_case_template_visa_types(
    actor_role_key: str, *, viewer_user_id: int | None = None
) -> list[dict]:
    """Визовые пути для шаблонов кейса — без админских ролей; «user» — только для владельца id=1."""
    out = [
        vt
        for vt in get_assignable_visa_types(actor_role_key)
        if vt.get("value") not in CASE_TEMPLATE_EXCLUDED_ROLE_KEYS
    ]
    uid = int(viewer_user_id or 0)
    if uid != GLOBAL_USER_ROLE_TEMPLATE_OWNER_ID:
        out = [vt for vt in out if vt.get("value") != "user"]
    return out


def can_manage_case_template_visa(
    actor_role_key: str,
    target_role_key: str,
    *,
    editor_user_id: int | None = None,
) -> bool:
    """Можно ли сохранять/читать шаблон для данного visa_type (роль клиента)."""
    normalized_target = normalize_role_key(target_role_key)
    if normalized_target in CASE_TEMPLATE_EXCLUDED_ROLE_KEYS:
        return False
    if normalized_target == "user":
        eid = int(editor_user_id or 0)
        if eid != GLOBAL_USER_ROLE_TEMPLATE_OWNER_ID:
            return False
    return can_assign_visa_type(actor_role_key, normalized_target)


def can_assign_visa_type(actor_role_key: str, target_role_key: str) -> bool:
    """Check if actor role can assign a specific role through 'Visa Path' field.
    
    This actually checks if actor can assign target_role_key to another user.
    """
    normalized_actor = normalize_role_key(actor_role_key)
    normalized_target = normalize_role_key(target_role_key)
    assignable_role_keys = ASSIGNABLE_VISA_TYPES_BY_ROLE.get(normalized_actor, ())
    return normalized_target in assignable_role_keys


def update_user_role(connection: sqlite3.Connection, user_id: int, role_key: str) -> bool:
    """Update user role and return True if a row was changed."""
    normalized_role = normalize_role_key(role_key)
    cursor = connection.execute(
        "UPDATE users SET role_key = ? WHERE id = ?",
        (normalized_role, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def update_user_profile(connection: sqlite3.Connection, user_id: int, payload: dict[str, Any]) -> bool:
    """Update editable profile fields."""
    cursor = connection.execute(
        """
        UPDATE users
        SET
            name = ?,
            email = ?,
            avatar = ?,
            phone = ?,
            main_goal = ?,
            locale = ?,
            notify_email = ?,
            notify_sms = ?,
            notify_whatsapp = ?
        WHERE id = ?
        """,
        (
            payload.get("name"),
            payload.get("email"),
            payload.get("avatar"),
            payload.get("phone"),
            payload.get("main_goal"),
            payload.get("locale"),
            1 if payload.get("notify_email") else 0,
            1 if payload.get("notify_sms") else 0,
            1 if payload.get("notify_whatsapp") else 0,
            user_id,
        ),
    )
    connection.commit()
    return cursor.rowcount > 0


def update_user_password(connection: sqlite3.Connection, user_id: int, password_hash: str) -> bool:
    """Update user password hash."""
    cursor = connection.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def set_email_verification_token(
    connection: sqlite3.Connection,
    user_id: int,
    token_hash: str,
    expires_at: str,
    sent_at: str,
) -> bool:
    """Store a hashed email verification token."""
    cursor = connection.execute(
        """
        UPDATE users
        SET
            email_verification_token_hash = ?,
            email_verification_expires_at = ?,
            email_verification_sent_at = ?
        WHERE id = ?
        """,
        (token_hash, expires_at, sent_at, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def get_user_by_email_verification_token_hash(
    connection: sqlite3.Connection, token_hash: str
):
    """Find a user by hashed email verification token."""
    cursor = connection.execute(
        """
        SELECT id, email, email_verified_at, email_verification_expires_at
        FROM users
        WHERE email_verification_token_hash = ?
        """,
        (token_hash,),
    )
    return cursor.fetchone()


def mark_user_email_verified(
    connection: sqlite3.Connection, user_id: int, verified_at: str
) -> bool:
    """Mark a user's email as verified and clear pending verification token."""
    cursor = connection.execute(
        """
        UPDATE users
        SET
            email_verified_at = ?,
            email_verification_token_hash = NULL,
            email_verification_expires_at = NULL,
            email_verification_sent_at = NULL
        WHERE id = ?
        """,
        (verified_at, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def set_password_reset_token(
    connection: sqlite3.Connection,
    user_id: int,
    token_hash: str,
    expires_at: str,
    requested_at: str,
) -> bool:
    """Store a hashed password reset token."""
    cursor = connection.execute(
        """
        UPDATE users
        SET
            password_reset_token_hash = ?,
            password_reset_expires_at = ?,
            password_reset_requested_at = ?
        WHERE id = ?
        """,
        (token_hash, expires_at, requested_at, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def get_user_by_password_reset_token_hash(
    connection: sqlite3.Connection, token_hash: str
):
    """Find a user by hashed password reset token."""
    cursor = connection.execute(
        """
        SELECT id, email, password_reset_expires_at
        FROM users
        WHERE password_reset_token_hash = ?
        """,
        (token_hash,),
    )
    return cursor.fetchone()


def update_user_password_and_clear_reset(
    connection: sqlite3.Connection,
    user_id: int,
    password_hash: str,
    revoked_at: str,
) -> bool:
    """Update password, clear reset token, and revoke existing auth tokens."""
    cursor = connection.execute(
        """
        UPDATE users
        SET
            password_hash = ?,
            password_reset_token_hash = NULL,
            password_reset_expires_at = NULL,
            password_reset_requested_at = NULL,
            auth_token_revoked_at = ?
        WHERE id = ?
        """,
        (password_hash, revoked_at, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def revoke_user_auth_tokens(
    connection: sqlite3.Connection, user_id: int, revoked_at: str
) -> bool:
    """Invalidate auth tokens issued before revoked_at."""
    cursor = connection.execute(
        "UPDATE users SET auth_token_revoked_at = ? WHERE id = ?",
        (revoked_at, user_id),
    )
    connection.commit()
    return cursor.rowcount > 0


def delete_user_by_id(connection: sqlite3.Connection, user_id: int) -> bool:
    """Delete user by id."""
    cursor = connection.execute("DELETE FROM users WHERE id = ?", (user_id,))
    connection.commit()
    return cursor.rowcount > 0


def create_manager_clients_table(connection: sqlite3.Connection) -> None:
    """Create manager_clients table for manager-client assignments."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS manager_clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            manager_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (manager_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (client_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(manager_id, client_id)
        )
        """
    )
    connection.commit()


def assign_client_to_manager(connection: sqlite3.Connection, manager_id: int, client_id: int) -> bool:
    """Assign a client to a manager."""
    try:
        connection.execute(
            "INSERT INTO manager_clients (manager_id, client_id) VALUES (?, ?)",
            (manager_id, client_id),
        )
        connection.commit()
        return True
    except sqlite3.IntegrityError:
        connection.rollback()
        return False


def is_client_assigned_to_manager(
    connection: sqlite3.Connection, manager_id: int, client_id: int
) -> bool:
    """True if this client row is linked to the manager in manager_clients."""
    row = connection.execute(
        "SELECT 1 FROM manager_clients WHERE manager_id = ? AND client_id = ?",
        (manager_id, client_id),
    ).fetchone()
    return bool(row)


def staff_may_access_target_user_workspace(
    connection: sqlite3.Connection, viewer_user_id: int, target_user_id: int
) -> bool:
    """
    Может ли персонал открывать «рабочее пространство» другого пользователя
    (клиенты, документы с userId, кейс): та же логика, что GET /users/<id> в lk.
    """
    if viewer_user_id == target_user_id:
        return True
    viewer = get_user_by_id(connection, viewer_user_id)
    target = get_user_by_id(connection, target_user_id)
    if not viewer or not target:
        return False
    role_key = normalize_role_key(viewer["role_key"] or "")
    role_data = get_role_definition(role_key)
    permissions = get_role_permissions(role_key)
    target_role_key = normalize_role_key(target["role_key"] or "")
    target_role_data = get_role_definition(target_role_key)

    if "full_access" in permissions or "view_all_users" in permissions:
        return True
    if "view_lower_users" in permissions:
        return float(target_role_data["level"]) >= float(role_data["level"])
    if "view_assignable_users" in permissions:
        return float(target_role_data["level"]) >= float(role_data["level"])
    if "view_assigned_clients" in permissions:
        return is_client_assigned_to_manager(connection, viewer_user_id, target_user_id)
    return False


def get_clients_for_manager(connection: sqlite3.Connection, manager_id: int) -> list:
    """Get all clients assigned to a specific manager."""
    cursor = connection.execute(
        """
        SELECT u.id, u.name, u.email, u.avatar, u.role_key, u.created_at, u.phone, u.display_id
        FROM users u
        INNER JOIN manager_clients mc ON u.id = mc.client_id
        WHERE mc.manager_id = ?
        ORDER BY u.created_at DESC
        """,
        (manager_id,),
    )
    return cursor.fetchall()


def get_users_by_role_level(connection: sqlite3.Connection, max_level: str) -> list:
    """Get all users with role level greater than or equal to max_level."""
    cursor = connection.execute(
        """
        SELECT id, name, email, avatar, role_key, created_at, phone, display_id
        FROM users
        ORDER BY created_at DESC
        """
    )
    all_users = cursor.fetchall()
    
    # Filter by role level
    filtered_users = []
    for user in all_users:
        role_key = normalize_role_key(user["role_key"] or "")
        role_def = get_role_definition(role_key)
        user_level = role_def["level"]
        
        # Compare levels (higher number = lower privilege)
        try:
            if float(user_level) >= float(max_level):
                filtered_users.append(user)
        except ValueError:
            continue
    
    return filtered_users


def get_all_users(connection: sqlite3.Connection) -> list:
    """Get all registered users."""
    cursor = connection.execute(
        """
        SELECT id, name, email, avatar, role_key, created_at, phone, display_id
        FROM users
        ORDER BY created_at DESC
        """
    )
    return cursor.fetchall()


def search_users_by_query(connection: sqlite3.Connection, query: str) -> list:
    """Search users by name or email."""
    search_pattern = f"%{query}%"
    cursor = connection.execute(
        """
        SELECT id, name, email, avatar, role_key, created_at, phone, display_id
        FROM users
        WHERE name LIKE ? OR email LIKE ?
        ORDER BY name ASC
        LIMIT 20
        """,
        (search_pattern, search_pattern)
    )
    return cursor.fetchall()


class User:
    """User class with static methods for easier access."""
    
    @staticmethod
    def get_by_id(user_id):
        """Get user by ID."""
        from utils.db import get_db_connection
        db = get_db_connection()
        cursor = db.execute(
            'SELECT id, name, email, role_key as role, avatar, phone FROM users WHERE id = ?',
            (user_id,)
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            result['full_name'] = result.get('name', 'Unknown')
            return result
        return None
    
    @staticmethod
    def search_users(query):
        """Search users by name or email."""
        from utils.db import get_db_connection
        db = get_db_connection()
        return search_users_by_query(db, query)
