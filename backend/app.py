"""Flask application entry point."""

import re
from pathlib import Path

from flask import Flask, g, jsonify, redirect, request, send_from_directory
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config, is_production_env
from models.document import create_documents_table, ensure_documents_columns
from models.security_log import create_security_logs_table
from models.user import (
    create_users_table,
    create_manager_clients_table,
    get_role_permissions,
    get_user_auth_by_id,
    get_user_by_id,
    normalize_role_key,
    staff_may_access_target_user_workspace,
)
from models.case_data import create_case_data_table
from models.case_history import create_case_history_table
from models.case_template import create_manager_case_templates_table
from models.manager_moderator import create_manager_moderators_table
from models.message import Message
from routes.auth import auth_bp
from routes.documents import documents_bp
from routes.health import health_bp
from routes.lk import lk_bp
from routes.user import user_bp
from routes.messages import messages_bp
from routes.admin_messages import admin_messages_bp
from routes.application_progress import bp as application_progress_bp
from routes.telegram_lk import telegram_lk_bp
from models.notifications import create_notification_tables
from services.auth_service import parse_storage_datetime
from utils.db import get_db_connection
from utils.rate_limiter import InMemoryRateLimiter
from utils.security import verify_auth_token


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUPPORTED_SITE_LANGUAGES = ("ru", "en")
LEGACY_RU_PAGE_REDIRECTS = {
    "servces.html": "/frontend/ru/services.html",
    "process.html": "/frontend/ru/process.html",
    "contact.html": "/frontend/ru/contact.html",
    "gold.html": "/frontend/ru/gold.html",
    "nomad.html": "/frontend/ru/nomad.html",
    "privacy-policy.html": "/frontend/ru/privacy-policy.html",
    "login.html": "/frontend/login.html",
}

# Versioned static assets (?v= in HTML) — long cache; HTML — revalidate each visit.
STATIC_LONG_CACHE_PREFIXES = ("/frontend/css/", "/frontend/js/", "/frontend/img/")
STATIC_LONG_CACHE_EXTENSIONS = (
    ".css",
    ".js",
    ".mjs",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".webmanifest",
)

DEFAULT_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.tailwindcss.com https://telegram.org 'unsafe-inline'; "
    "style-src 'self' https://fonts.googleapis.com 'unsafe-inline'; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob: https://lh3.googleusercontent.com https:; "
    "connect-src 'self'; "
    "frame-src https://oauth.telegram.org; "
    "object-src 'none'; "
    "frame-ancestors 'none'"
)
DEFAULT_PERMISSIONS_POLICY = "geolocation=(), camera=(), microphone=()"
RATE_LIMIT_AUTH_PATHS = frozenset(
    {
        "/api/login",
        "/api/login/telegram",
        "/api/register",
        "/api/forgot-password",
        "/api/reset-password",
        "/api/resend-verification",
    }
)
RATE_LIMIT_DOCUMENT_REPLACE_PATH_RE = re.compile(r"^/api/documents/\d+/replace$")
RATE_LIMIT_CASE_ARCHIVE_PATH_RE = re.compile(r"^/api/case-data/\d+/archive$")
RATE_LIMIT_MESSAGE_POST_PATH_RE = re.compile(r"^/api/conversations/[^/]+/messages$")
RATE_LIMITER = InMemoryRateLimiter()


def _static_cache_policy(path: str) -> str | None:
    """Return Cache-Control value or None to leave response unchanged."""
    normalized = path.split("?", 1)[0].lower()
    if normalized.endswith(".html"):
        return "no-cache"
    if normalized.startswith(STATIC_LONG_CACHE_PREFIXES):
        return "public, max-age=31536000, immutable"
    if normalized.startswith("/frontend/") and normalized.endswith(STATIC_LONG_CACHE_EXTENSIONS):
        return "public, max-age=31536000, immutable"
    return None


def detect_preferred_site_language() -> str:
    preferred = request.accept_languages.best_match(SUPPORTED_SITE_LANGUAGES)
    if preferred in SUPPORTED_SITE_LANGUAGES:
        return preferred
    return "ru"


def _extract_auth_cookie_token() -> str:
    return (request.cookies.get("access_token") or "").strip()


def _append_vary_header(response, value: str) -> None:
    current = response.headers.get("Vary")
    if not current:
        response.headers["Vary"] = value
        return
    vary_values = {item.strip() for item in current.split(",") if item.strip()}
    if value not in vary_values:
        response.headers["Vary"] = f"{current}, {value}"


def _is_https_request() -> bool:
    if request.is_secure:
        return True
    forwarded_proto = (request.headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip().lower()
    return forwarded_proto == "https"


def _apply_security_headers(response):
    response.headers["Content-Security-Policy"] = DEFAULT_CONTENT_SECURITY_POLICY
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = DEFAULT_PERMISSIONS_POLICY
    if _is_https_request():
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


def _request_ip() -> str:
    forwarded_for = request.headers.get("X-Forwarded-For", "")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    return (request.remote_addr or "").strip()


def _extract_request_email() -> str:
    payload = request.get_json(silent=True) or {}
    email = payload.get("email")
    if email is None:
        email = request.form.get("email", "")
    return str(email or "").strip().lower()


def _is_auth_rate_limited_path(path: str) -> bool:
    return request.method == "POST" and path in RATE_LIMIT_AUTH_PATHS


def _is_upload_rate_limited_path(path: str) -> bool:
    if request.method != "POST":
        return False
    if path == "/api/documents/upload":
        return True
    if RATE_LIMIT_DOCUMENT_REPLACE_PATH_RE.fullmatch(path):
        return True
    return bool(RATE_LIMIT_CASE_ARCHIVE_PATH_RE.fullmatch(path))


def _is_message_rate_limited_path(path: str) -> bool:
    if request.method != "POST":
        return False
    return bool(RATE_LIMIT_MESSAGE_POST_PATH_RE.fullmatch(path))


def _rate_limit_rejected_response(scope: str, retry_after_seconds: int):
    response = jsonify(
        {
            "success": False,
            "error": "rate limit exceeded",
            "scope": scope,
            "retry_after_seconds": int(retry_after_seconds),
        }
    )
    response.status_code = 429
    response.headers["Retry-After"] = str(int(retry_after_seconds))
    return response


def _check_rate_limit(limit_key: str, max_requests: int, window_seconds: int) -> tuple[bool, int]:
    safe_max = max(1, int(max_requests))
    safe_window = max(1, int(window_seconds))
    return RATE_LIMITER.check(limit_key, safe_max, safe_window)


def _normalize_origin(value: str | None) -> str:
    if not value:
        return ""
    return value.strip().rstrip("/").lower()


def _is_allowed_cors_origin(app: Flask, origin: str | None) -> bool:
    normalized_origin = _normalize_origin(origin)
    if not normalized_origin:
        return False
    allowed_origins = app.config.get("CORS_ALLOWED_ORIGINS", tuple())
    if allowed_origins and normalized_origin in {
        _normalize_origin(item) for item in allowed_origins
    }:
        return True
    # Local dev: Live Server / Vite on other ports still talk to Flask on :5000.
    if app.config.get("DEBUG") or not is_production_env():
        if normalized_origin.startswith("http://localhost:") or normalized_origin.startswith(
            "http://127.0.0.1:"
        ):
            return True
    return False


def _viewer_permissions_for_storage(db, viewer_user_id: int) -> set[str]:
    viewer = get_user_by_id(db, int(viewer_user_id))
    if not viewer:
        return set()
    return set(get_role_permissions(normalize_role_key(viewer["role_key"] or "")))


def _may_access_document_file(db, viewer_user_id: int, owner_user_id: int) -> bool:
    if int(viewer_user_id) == int(owner_user_id):
        return True
    permissions = _viewer_permissions_for_storage(db, int(viewer_user_id))
    if not permissions:
        return False
    can_download_documents = bool(
        {"full_access", "download_documents", "review_documents", "approve_documents"} & permissions
    )
    if not can_download_documents:
        return False
    return staff_may_access_target_user_workspace(db, int(viewer_user_id), int(owner_user_id))


def _may_access_case_archive(db, viewer_user_id: int, owner_user_id: int) -> bool:
    if int(viewer_user_id) == int(owner_user_id):
        return True
    permissions = _viewer_permissions_for_storage(db, int(viewer_user_id))
    if not permissions:
        return False
    has_case_read_capability = bool(
        {
            "full_access",
            "view_all_users",
            "view_lower_users",
            "view_assignable_users",
            "view_assigned_clients",
            "communicate_with_clients",
            "respond_to_applications",
            "review_documents",
            "approve_documents",
            "download_documents",
        }
        & permissions
    )
    if not has_case_read_capability:
        return False
    return staff_may_access_target_user_workspace(db, int(viewer_user_id), int(owner_user_id))


def _is_allowed_message_file_for_user(db, viewer_user_id: int, file_path: str) -> bool:
    message_row = db.execute(
        """
        SELECT sender_id, receiver_id
        FROM messages
        WHERE image_path = ? OR file_path = ?
        LIMIT 1
        """,
        (file_path, file_path),
    ).fetchone()
    if not message_row:
        return False
    if int(viewer_user_id) in (int(message_row["sender_id"]), int(message_row["receiver_id"])):
        return True
    permissions = _viewer_permissions_for_storage(db, int(viewer_user_id))
    return "full_access" in permissions


def _is_allowed_storage_file_for_user(db, viewer_user_id: int, file_path: str) -> bool:
    doc_row = db.execute(
        "SELECT user_id FROM documents WHERE file_path = ? LIMIT 1", (file_path,)
    ).fetchone()
    if doc_row:
        return _may_access_document_file(db, int(viewer_user_id), int(doc_row["user_id"]))

    case_archive_row = db.execute(
        "SELECT user_id FROM case_data WHERE archive_file_path = ? LIMIT 1", (file_path,)
    ).fetchone()
    if case_archive_row:
        return _may_access_case_archive(db, int(viewer_user_id), int(case_archive_row["user_id"]))

    return _is_allowed_message_file_for_user(db, int(viewer_user_id), file_path)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["ENV"] = "production" if is_production_env() else "development"

    app.register_blueprint(auth_bp, url_prefix="/api")
    app.register_blueprint(documents_bp, url_prefix="/api")
    app.register_blueprint(health_bp, url_prefix="/api")
    app.register_blueprint(lk_bp, url_prefix="/api")
    app.register_blueprint(user_bp, url_prefix="/api")
    app.register_blueprint(messages_bp)
    app.register_blueprint(admin_messages_bp)
    app.register_blueprint(application_progress_bp)
    app.register_blueprint(telegram_lk_bp, url_prefix="/api/lk")

    init_connection = get_db_connection()
    create_users_table(init_connection)
    create_documents_table(init_connection)
    ensure_documents_columns(init_connection)
    create_security_logs_table(init_connection)
    create_manager_clients_table(init_connection)
    create_manager_moderators_table(init_connection)
    create_case_data_table(init_connection)
    create_case_history_table(init_connection)
    create_manager_case_templates_table(init_connection)
    create_notification_tables(init_connection)
    Message.create_table()
    init_connection.close()

    @app.before_request
    def open_db_connection():
        g.db = get_db_connection()
        g.current_user_id = None

    @app.before_request
    def handle_api_preflight():
        if request.method != "OPTIONS" or not request.path.startswith("/api/"):
            return None
        return ("", 204)

    @app.before_request
    def require_token_for_protected_api():
        protected_paths = ("/api/lk", "/api/user", "/api/users", "/api/roles", "/api/documents", "/api/document-history", "/api/application", "/api/case-data", "/api/case-history", "/api/case-templates", "/api/conversations", "/api/messages", "/api/admin", "/api/logout")
        if not request.path.startswith(protected_paths):
            return None

        token = _extract_auth_cookie_token()

        if not token:
            return jsonify({"success": False, "error": "missing token"}), 401

        payload = verify_auth_token(
            app.config["SECRET_KEY"],
            token,
            max_age_seconds=7 * 24 * 60 * 60,
        )
        if not payload or "user_id" not in payload:
            return jsonify({"success": False, "error": "invalid token"}), 401

        user = get_user_auth_by_id(g.db, int(payload["user_id"]))
        if not user:
            return jsonify({"success": False, "error": "invalid token"}), 401

        revoked_at = parse_storage_datetime(user["auth_token_revoked_at"])
        issued_at = payload.get("issued_at")
        if revoked_at and (not issued_at or issued_at <= int(revoked_at.timestamp())):
            return jsonify({"success": False, "error": "token revoked"}), 401

        if user["deletion_requested_at"]:
            return jsonify({"success": False, "error": "account deletion pending"}), 403

        g.current_user_id = payload["user_id"]
        return None

    @app.before_request
    def enforce_rate_limits():
        if not app.config.get("RATE_LIMIT_ENABLED", True):
            return None
        if request.method == "OPTIONS":
            return None

        path = request.path
        ip = _request_ip() or "unknown"

        if _is_auth_rate_limited_path(path):
            allowed, retry_after = _check_rate_limit(
                f"auth:ip:{path}:{ip}",
                app.config["AUTH_RATE_LIMIT_IP_MAX"],
                app.config["AUTH_RATE_LIMIT_IP_WINDOW_SECONDS"],
            )
            if not allowed:
                return _rate_limit_rejected_response("auth_ip", retry_after)

            email = _extract_request_email()
            if email:
                allowed, retry_after = _check_rate_limit(
                    f"auth:email:{path}:{email}",
                    app.config["AUTH_RATE_LIMIT_EMAIL_MAX"],
                    app.config["AUTH_RATE_LIMIT_EMAIL_WINDOW_SECONDS"],
                )
                if not allowed:
                    return _rate_limit_rejected_response("auth_email", retry_after)
            return None

        if _is_upload_rate_limited_path(path):
            allowed, retry_after = _check_rate_limit(
                f"upload:ip:{path}:{ip}",
                app.config["UPLOAD_RATE_LIMIT_IP_MAX"],
                app.config["UPLOAD_RATE_LIMIT_IP_WINDOW_SECONDS"],
            )
            if not allowed:
                return _rate_limit_rejected_response("upload_ip", retry_after)

            if g.get("current_user_id"):
                allowed, retry_after = _check_rate_limit(
                    f"upload:user:{path}:{int(g.current_user_id)}",
                    app.config["UPLOAD_RATE_LIMIT_USER_MAX"],
                    app.config["UPLOAD_RATE_LIMIT_USER_WINDOW_SECONDS"],
                )
                if not allowed:
                    return _rate_limit_rejected_response("upload_user", retry_after)
            return None

        if _is_message_rate_limited_path(path):
            allowed, retry_after = _check_rate_limit(
                f"message:ip:{path}:{ip}",
                app.config["MESSAGE_RATE_LIMIT_IP_MAX"],
                app.config["MESSAGE_RATE_LIMIT_IP_WINDOW_SECONDS"],
            )
            if not allowed:
                return _rate_limit_rejected_response("message_ip", retry_after)

            if g.get("current_user_id"):
                allowed, retry_after = _check_rate_limit(
                    f"message:user:{path}:{int(g.current_user_id)}",
                    app.config["MESSAGE_RATE_LIMIT_USER_MAX"],
                    app.config["MESSAGE_RATE_LIMIT_USER_WINDOW_SECONDS"],
                )
                if not allowed:
                    return _rate_limit_rejected_response("message_user", retry_after)
            return None

        return None

    @app.after_request
    def add_api_cors_headers(response):
        if request.path.startswith("/api/"):
            origin = request.headers.get("Origin")
            if _is_allowed_cors_origin(app, origin):
                response.headers["Access-Control-Allow-Origin"] = origin
                _append_vary_header(response, "Origin")
                response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            return _apply_security_headers(response)

        if request.method == "GET" and response.status_code == 200:
            cache_policy = _static_cache_policy(request.path)
            if cache_policy:
                response.headers["Cache-Control"] = cache_policy

        return _apply_security_headers(response)

    @app.teardown_request
    def close_db_connection(exception):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    @app.route("/")
    @app.route("/index.html")
    @app.route("/frontend/")
    @app.route("/frontend/index.html")
    def redirect_to_localized_home():
        language = detect_preferred_site_language()
        return redirect(f"/frontend/{language}/index.html")

    def _unified_login_redirect(lang: str):
        from urllib.parse import urlencode

        params = request.args.to_dict(flat=True)
        params["lang"] = lang
        return redirect(f"/frontend/login.html?{urlencode(params)}")

    @app.route("/frontend/login.html")
    def serve_login_page():
        return send_from_directory(str(PROJECT_ROOT / "frontend"), "login.html")

    @app.route("/frontend/ru/login.html")
    def redirect_ru_login_page():
        return _unified_login_redirect("ru")

    @app.route("/frontend/en/login.html")
    def redirect_en_login_page():
        return _unified_login_redirect("en")

    @app.route("/storage/<path:filepath>")
    def serve_storage_file(filepath: str):
        """Serve files from storage directory with strict ACL checks."""
        storage_path = PROJECT_ROOT / "storage"
        requested_file = (storage_path / filepath).resolve()

        # Protect against path traversal
        if storage_path not in requested_file.parents and requested_file.parent != storage_path:
            return jsonify({"success": False, "error": "not found"}), 404

        if not requested_file.is_file():
            return jsonify({"success": False, "error": "not found"}), 404

        token = _extract_auth_cookie_token()
        if not token:
            return jsonify({"success": False, "error": "missing token"}), 401

        payload = verify_auth_token(
            app.config["SECRET_KEY"],
            token,
            max_age_seconds=7 * 24 * 60 * 60,
        )
        if not payload or "user_id" not in payload:
            return jsonify({"success": False, "error": "invalid token"}), 401

        user = get_user_auth_by_id(g.db, int(payload["user_id"]))
        if not user:
            return jsonify({"success": False, "error": "invalid token"}), 401

        revoked_at = parse_storage_datetime(user["auth_token_revoked_at"])
        issued_at = payload.get("issued_at")
        if revoked_at and (not issued_at or issued_at <= int(revoked_at.timestamp())):
            return jsonify({"success": False, "error": "token revoked"}), 401

        normalized_path = filepath.replace("\\", "/")
        if not _is_allowed_storage_file_for_user(g.db, int(payload["user_id"]), normalized_path):
            return jsonify({"success": False, "error": "forbidden"}), 403

        return send_from_directory(str(storage_path), normalized_path)

        return jsonify({"success": False, "error": "not found"}), 404

    @app.route("/<path:requested_path>")
    def serve_site_files(requested_path: str):
        if requested_path.startswith("api/"):
            return jsonify({"success": False, "error": "not found"}), 404

        if requested_path in LEGACY_RU_PAGE_REDIRECTS:
            return redirect(LEGACY_RU_PAGE_REDIRECTS[requested_path])

        requested_file = (PROJECT_ROOT / requested_path).resolve()

        # Protect against path traversal outside the project directory.
        if PROJECT_ROOT not in requested_file.parents and requested_file != PROJECT_ROOT:
            return jsonify({"success": False, "error": "not found"}), 404

        if requested_file.is_file():
            return send_from_directory(str(PROJECT_ROOT), requested_path)

        if requested_file.is_dir():
            index_file = requested_file / "index.html"
            if index_file.is_file():
                relative_index = index_file.relative_to(PROJECT_ROOT)
                return send_from_directory(str(PROJECT_ROOT), str(relative_index))

        return send_from_directory(str(PROJECT_ROOT), "404.html"), 404

    @app.errorhandler(404)
    def handle_404(error):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "not found"}), 404
        return send_from_directory(str(PROJECT_ROOT), "404.html"), 404

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(error):
        if request.path.startswith("/api/"):
            return jsonify({"success": False, "error": "file too large"}), 413
        return send_from_directory(str(PROJECT_ROOT), "404.html"), 413

    return app


app = create_app()


def _run_dev_server() -> None:
    """Built-in server for local development only (not for production)."""
    import sys

    if is_production_env():
        print(
            "Refusing app.run() in production. Use a WSGI server, e.g.:\n"
            "  waitress-serve --listen=127.0.0.1:5000 wsgi:application",
            file=sys.stderr,
        )
        raise SystemExit(1)

    debug = bool(app.config.get("DEBUG"))
    use_reloader = debug and bool(app.config.get("FLASK_USE_RELOADER", True))
    app.run(
        host=app.config.get("FLASK_RUN_HOST", "127.0.0.1"),
        port=int(app.config.get("FLASK_RUN_PORT", 5000)),
        debug=debug,
        use_reloader=use_reloader,
    )


if __name__ == "__main__":
    _run_dev_server()
