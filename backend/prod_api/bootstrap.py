"""Bootstrap data for production API."""

from __future__ import annotations

import json
import os

from werkzeug.security import generate_password_hash

from backend.prod_api.db import get_connection


DEFAULT_CLIENT_PERMISSIONS = ["upload_documents", "download_documents"]


def ensure_bootstrap_admin() -> None:
    admin_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip().lower()
    admin_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    admin_name = os.getenv("BOOTSTRAP_ADMIN_NAME", "Platform Admin").strip() or "Platform Admin"
    admin_role = os.getenv("BOOTSTRAP_ADMIN_ROLE", "management").strip() or "management"

    if not admin_email or not admin_password:
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users WHERE email = %s", (admin_email,))
            existing = cur.fetchone()
            if existing:
                return

            cur.execute(
                """
                INSERT INTO users (email, password_hash, name, role_key, permissions, case_status)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                """,
                (
                    admin_email,
                    generate_password_hash(admin_password),
                    admin_name,
                    admin_role,
                    '["full_access","view_all_users","approve_documents","review_documents","download_documents"]',
                    "active",
                ),
            )

            # Optional demo user to make initial UI contract predictable.
            demo_email = os.getenv("BOOTSTRAP_DEMO_EMAIL", "").strip().lower()
            demo_password = os.getenv("BOOTSTRAP_DEMO_PASSWORD", "").strip()
            if demo_email and demo_password:
                cur.execute("SELECT id FROM users WHERE email = %s", (demo_email,))
                if not cur.fetchone():
                    cur.execute(
                        """
                        INSERT INTO users (email, password_hash, name, role_key, permissions, case_status)
                        VALUES (%s, %s, %s, %s, %s::jsonb, %s)
                        """,
                        (
                            demo_email,
                            generate_password_hash(demo_password),
                            os.getenv("BOOTSTRAP_DEMO_NAME", "Demo Client"),
                            "user",
                            json.dumps(DEFAULT_CLIENT_PERMISSIONS),
                            "onboarding",
                        ),
                    )

        conn.commit()
