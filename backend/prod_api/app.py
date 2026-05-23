"""Production-ready minimal API for frontend contract."""

from __future__ import annotations

import os
from functools import wraps

from flask import Flask, g, jsonify, make_response, request
from werkzeug.security import check_password_hash

from backend.prod_api.auth import decode_token, issue_token, read_token_from_request
from backend.prod_api.bootstrap import ensure_bootstrap_admin
from backend.prod_api.db import get_connection
from backend.prod_api.migrate import run_migrations


ROLE_LEVELS = {
    "management": 1,
    "admin": 2,
    "moderator": 3,
    "manager": 4,
    "user": 5,
}


def _role_payload(role_key: str) -> dict:
    key = (role_key or "user").strip().lower() or "user"
    return {
        "key": key,
        "level": ROLE_LEVELS.get(key, 5),
        "name_ru": key,
    }


def _load_permissions(raw_permissions) -> list[str]:
    if isinstance(raw_permissions, list):
        return [str(item) for item in raw_permissions]
    return []


def _to_user_payload(row: dict) -> dict:
    permissions = _load_permissions(row.get("permissions"))
    return {
        "id": row["id"],
        "email": row["email"] or "",
        "name": row.get("name") or "",
        "role": _role_payload(row.get("role_key") or "user"),
        "permissions": permissions,
        "case_status": row.get("case_status") or "unknown",
        "application_status": row.get("case_status") or "unknown",
        "display_id": row.get("display_id"),
    }


def _require_auth(handler):
    @wraps(handler)
    def wrapped(*args, **kwargs):
        token = read_token_from_request(request)
        payload = decode_token(token)
        if not payload or "sub" not in payload:
            return jsonify({"success": False, "error": "invalid token"}), 401
        g.current_user_id = int(payload["sub"])
        return handler(*args, **kwargs)

    return wrapped


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["JSON_AS_ASCII"] = False

    @app.before_request
    def open_db():
        g.db = get_connection()

    @app.teardown_request
    def close_db(_exception):
        db = g.pop("db", None)
        if db:
            db.close()

    @app.get("/api/health")
    def health():
        return jsonify({"success": True, "service": "spainza-backend"}), 200

    @app.get("/api/health/db")
    def health_db():
        with g.db.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
        return jsonify({"success": True, "db": "ok"}), 200

    @app.post("/api/login")
    def login():
        payload = request.get_json(silent=True) or {}
        email = str(payload.get("email") or "").strip().lower()
        password = str(payload.get("password") or "")
        if not email or not password:
            return jsonify({"success": False, "error": "email and password required"}), 400

        with g.db.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, name, role_key, permissions, case_status, display_id
                FROM users
                WHERE email = %s
                LIMIT 1
                """,
                (email,),
            )
            user = cur.fetchone()

        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"success": False, "error": "invalid credentials"}), 401

        token = issue_token(int(user["id"]))
        response = make_response(
            jsonify(
                {
                    "success": True,
                    "token": token,
                    "user": _to_user_payload(user),
                }
            ),
            200,
        )
        response.set_cookie(
            "access_token",
            token,
            httponly=True,
            samesite="Lax",
            secure=os.getenv("COOKIE_SECURE", "1").strip().lower() not in {"0", "false", "no"},
            max_age=7 * 24 * 60 * 60,
            path="/",
        )
        return response

    @app.get("/api/lk/session")
    @_require_auth
    def session_check():
        return jsonify({"success": True, "user_id": g.current_user_id}), 200

    @app.get("/api/user")
    @_require_auth
    def user_profile():
        with g.db.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, name, role_key, permissions, case_status, display_id
                FROM users
                WHERE id = %s
                LIMIT 1
                """,
                (g.current_user_id,),
            )
            user = cur.fetchone()
        if not user:
            return jsonify({"success": False, "error": "user not found"}), 404
        payload = _to_user_payload(user)
        payload["success"] = True
        return jsonify(payload), 200

    @app.get("/api/documents")
    @_require_auth
    def documents():
        requested_user_id = request.args.get("userId", type=int) or g.current_user_id
        if requested_user_id != g.current_user_id:
            with g.db.cursor() as cur:
                cur.execute("SELECT role_key FROM users WHERE id = %s", (g.current_user_id,))
                viewer = cur.fetchone()
            if not viewer or (viewer.get("role_key") or "").strip().lower() not in {"management", "admin"}:
                return jsonify({"success": False, "error": "forbidden"}), 403

        with g.db.cursor() as cur:
            cur.execute(
                """
                SELECT id, title, status, file_type, file_size, created_at
                FROM documents
                WHERE user_id = %s
                ORDER BY created_at DESC, id DESC
                """,
                (requested_user_id,),
            )
            rows = cur.fetchall()

        data = [
            {
                "id": row["id"],
                "title": row.get("title") or "",
                "status": row.get("status") or "pending",
                "file_type": row.get("file_type") or "FILE",
                "file_size": row.get("file_size") or "",
                "last_action_at": (row.get("created_at").isoformat() if row.get("created_at") else ""),
                "source": "uploaded",
                "is_priority": False,
                "icon": "description",
            }
            for row in rows
        ]
        return jsonify({"success": True, "documents": data}), 200

    return app


run_migrations()
ensure_bootstrap_admin()
app = create_app()

