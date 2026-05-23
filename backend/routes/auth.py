"""Authentication routes."""

from sqlite3 import IntegrityError

from flask import Blueprint, current_app, g, jsonify, request, make_response

from models.security_log import add_security_log
from models.user import create_user, get_user_by_email, revoke_user_auth_tokens
from services.auth_service import (
    issue_email_verification_token,
    issue_password_reset_token,
    is_email_verification_pending,
    reset_password_with_token,
    send_password_reset_email,
    send_verification_email,
    to_storage_datetime,
    utc_now,
    verify_email_token,
)
from services.case_template_apply import materialize_case_from_template_if_needed
from services.manager_client_assign import (
    resolve_manager_id_from_invite_token,
    try_assign_client_to_manager,
)
from services.welcome_support_message import send_support_welcome_to_new_user
from utils.security import (
    generate_auth_token,
    hash_password,
    is_valid_email,
    is_valid_password,
    verify_password,
)

auth_bp = Blueprint("auth", __name__)
AUTH_COOKIE_NAME = "access_token"


def _error_response(error_code: str, message_ru: str, message_en: str, status_code: int):
    return (
        jsonify(
            {
                "success": False,
                "error_code": error_code,
                "message_ru": message_ru,
                "message_en": message_en,
            }
        ),
        status_code,
    )


def _extract_credentials():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    password = payload.get("password") or ""
    manager_invite_token = (payload.get("manager_invite_token") or "").strip()
    return email, password, manager_invite_token


def _request_ip() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.remote_addr or "").strip()


def _is_request_secure() -> bool:
    if request.is_secure:
        return True
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").split(",")[0].strip().lower()
    return forwarded_proto == "https"


def _auth_cookie_attrs() -> tuple[bool, str]:
    """Same-site Lax cookie; Secure only on HTTPS (works on http://localhost)."""
    return _is_request_secure(), "Lax"


def _set_auth_cookie(response, token: str):
    secure_cookie, same_site = _auth_cookie_attrs()
    response.set_cookie(
        AUTH_COOKIE_NAME,
        token,
        httponly=True,
        secure=secure_cookie,
        samesite=same_site,
        path="/",
        max_age=7 * 24 * 60 * 60,
    )


def _clear_auth_cookie(response):
    secure_cookie, same_site = _auth_cookie_attrs()
    response.set_cookie(
        AUTH_COOKIE_NAME,
        "",
        httponly=True,
        secure=secure_cookie,
        samesite=same_site,
        path="/",
        expires=0,
        max_age=0,
    )


@auth_bp.post("/register")
def register():
    email, password, manager_invite_token = _extract_credentials()
    if not email:
        return _error_response(
            "MISSING_EMAIL",
            "Введите email",
            "Please enter your email",
            400,
        )
    if not password:
        return _error_response(
            "MISSING_PASSWORD",
            "Введите пароль",
            "Please enter your password",
            400,
        )
    if not is_valid_email(email):
        return _error_response(
            "INVALID_EMAIL",
            "Некорректный формат email",
            "Invalid email format",
            400,
        )
    if not is_valid_password(password):
        return _error_response(
            "INVALID_PASSWORD",
            "Пароль должен содержать минимум 8 символов, одну строчную букву и одну заглавную",
            "Password must include at least 8 characters, one lowercase letter, and one uppercase letter",
            400,
        )

    if get_user_by_email(g.db, email):
        return _error_response(
            "USER_ALREADY_EXISTS",
            "Пользователь с таким email уже существует",
            "A user with this email already exists",
            409,
        )

    try:
        user_id, display_id = create_user(g.db, email, hash_password(password))
    except IntegrityError:
        return _error_response(
            "USER_ALREADY_EXISTS",
            "Пользователь с таким email уже существует",
            "A user with this email already exists",
            409,
        )

    verification_token = ""
    verification_expires_at = ""
    verification_delivery = {"sent": False, "reason": "not_attempted"}
    try:
        verification_token, verification_expires_at = issue_email_verification_token(g.db, user_id)
        verification_delivery = send_verification_email(email, verification_token)
    except Exception as exc:
        current_app.logger.exception("email verification after register failed: %s", exc)
        verification_delivery = {"sent": False, "reason": "send_failed"}

    try:
        materialize_case_from_template_if_needed(g.db, user_id, fallback_viewer_id=None)
    except Exception as exc:
        current_app.logger.exception("case template materialize after register: %s", exc)

    if manager_invite_token:
        mgr_id = resolve_manager_id_from_invite_token(g.db, manager_invite_token)
        if mgr_id:
            try:
                ok, code = try_assign_client_to_manager(g.db, mgr_id, user_id)
                if not ok and code != "personal_manager_taken":
                    current_app.logger.warning(
                        "register invite assign: user_id=%s manager_id=%s code=%s",
                        user_id,
                        mgr_id,
                        code,
                    )
            except Exception as exc:
                current_app.logger.exception("register invite assign failed: %s", exc)

    try:
        send_support_welcome_to_new_user(g.db, user_id)
    except Exception as exc:
        current_app.logger.exception("welcome support message after register: %s", exc)

    return (
        jsonify(
            {
                "success": True,
                "user_id": user_id,
                "display_id": display_id,
                "verification_required": True,
                "verification_expires_at": verification_expires_at,
                "email_delivery": verification_delivery,
            }
        ),
        201,
    )


@auth_bp.post("/login")
def login():
    email, password, _invite = _extract_credentials()
    if not email:
        return _error_response(
            "MISSING_EMAIL",
            "Введите email",
            "Please enter your email",
            400,
        )
    if not password:
        return _error_response(
            "MISSING_PASSWORD",
            "Введите пароль",
            "Please enter your password",
            400,
        )
    if not is_valid_email(email):
        return _error_response(
            "INVALID_EMAIL",
            "Некорректный формат email",
            "Invalid email format",
            400,
        )

    user = get_user_by_email(g.db, email)
    if not user or not verify_password(password, user["password_hash"]):
        return _error_response(
            "INVALID_CREDENTIALS",
            "Неверный email или пароль",
            "Incorrect email or password",
            401,
        )
    token = generate_auth_token(current_app.config["SECRET_KEY"], user["id"])
    response = make_response(
        jsonify({"success": True, "user_id": user["id"], "email": user["email"]}),
        200,
    )
    _set_auth_cookie(response, token)
    return response


@auth_bp.route("/verify-email", methods=["GET", "POST"])
def verify_email():
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or request.args.get("token") or "").strip()
    if not token:
        return _error_response(
            "MISSING_TOKEN",
            "Ссылка подтверждения некорректна",
            "Verification link is invalid",
            400,
        )

    ok, code, user_id = verify_email_token(g.db, token)
    if not ok:
        if code == "expired_token":
            return _error_response(
                "EXPIRED_TOKEN",
                "Ссылка подтверждения истекла. Запросите письмо повторно.",
                "Verification link expired. Please request a new email.",
                400,
            )
        return _error_response(
            "INVALID_TOKEN",
            "Ссылка подтверждения некорректна",
            "Verification link is invalid",
            400,
        )

    if user_id:
        try:
            add_security_log(
                g.db,
                user_id,
                "email_verified",
                "Email подтверждён",
                details="Аккаунт активирован через ссылку подтверждения.",
                ip_address=_request_ip(),
            )
        except Exception as exc:
            current_app.logger.exception("email verified security log failed: %s", exc)

    return jsonify({"success": True, "status": code}), 200


@auth_bp.post("/resend-verification")
def resend_verification():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    if not email or not is_valid_email(email):
        return _error_response(
            "INVALID_EMAIL",
            "Некорректный формат email",
            "Invalid email format",
            400,
        )

    user = get_user_by_email(g.db, email)
    if not user:
        return jsonify({"success": True}), 200
    if not is_email_verification_pending(user):
        return jsonify({"success": True, "already_verified": True}), 200

    token, expires_at = issue_email_verification_token(g.db, int(user["id"]))
    delivery = send_verification_email(email, token)
    return (
        jsonify(
            {
                "success": True,
                "verification_expires_at": expires_at,
                "email_delivery": delivery,
            }
        ),
        200,
    )


@auth_bp.post("/forgot-password")
def forgot_password():
    payload = request.get_json(silent=True) or {}
    email = (payload.get("email") or "").strip().lower()
    if not email or not is_valid_email(email):
        return _error_response(
            "INVALID_EMAIL",
            "Некорректный формат email",
            "Invalid email format",
            400,
        )

    user = get_user_by_email(g.db, email)
    if user:
        try:
            token, _expires_at = issue_password_reset_token(g.db, int(user["id"]))
            send_password_reset_email(email, token)
        except Exception as exc:
            current_app.logger.exception("forgot password email failed: %s", exc)

    response = make_response(jsonify({"success": True}), 200)
    _clear_auth_cookie(response)
    return response


@auth_bp.post("/reset-password")
def reset_password():
    payload = request.get_json(silent=True) or {}
    token = (payload.get("token") or "").strip()
    password = payload.get("password") or ""
    if not token:
        return _error_response(
            "MISSING_TOKEN",
            "Ссылка восстановления некорректна",
            "Password reset link is invalid",
            400,
        )
    if not is_valid_password(password):
        return _error_response(
            "INVALID_PASSWORD",
            "Пароль должен содержать минимум 8 символов, одну строчную букву и одну заглавную",
            "Password must include at least 8 characters, one lowercase letter, and one uppercase letter",
            400,
        )

    ok, code, user_id = reset_password_with_token(g.db, token, password)
    if not ok:
        if code == "expired_token":
            return _error_response(
                "EXPIRED_TOKEN",
                "Ссылка восстановления истекла. Запросите письмо повторно.",
                "Password reset link expired. Please request a new email.",
                400,
            )
        return _error_response(
            "INVALID_TOKEN",
            "Ссылка восстановления некорректна",
            "Password reset link is invalid",
            400,
        )

    if user_id:
        add_security_log(
            g.db,
            user_id,
            "password_reset",
            "Пароль восстановлен",
            details="Пароль изменён через ссылку восстановления. Старые сессии отозваны.",
            ip_address=_request_ip(),
        )

    return jsonify({"success": True, "status": code}), 200


@auth_bp.post("/logout")
def logout():
    user_id = g.current_user_id
    if not user_id:
        return jsonify({"success": False, "error": "missing token"}), 401

    revoked_at = to_storage_datetime(utc_now())
    revoke_user_auth_tokens(g.db, int(user_id), revoked_at)
    add_security_log(
        g.db,
        int(user_id),
        "logout",
        "Выход из аккаунта",
        details="Текущие токены авторизации отозваны на сервере.",
        ip_address=_request_ip(),
    )
    response = make_response(jsonify({"success": True}), 200)
    _clear_auth_cookie(response)
    return response
