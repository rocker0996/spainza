"""Simple SQL migration runner."""

from __future__ import annotations

from pathlib import Path

from backend.prod_api.db import get_connection


MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def run_migrations() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        return

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )

            for migration_file in migration_files:
                version = migration_file.name
                cur.execute(
                    "SELECT 1 FROM schema_migrations WHERE version = %s",
                    (version,),
                )
                if cur.fetchone():
                    continue

                cur.execute(migration_file.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO schema_migrations(version) VALUES (%s)",
                    (version,),
                )

        conn.commit()
