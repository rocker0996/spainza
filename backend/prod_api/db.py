"""PostgreSQL helpers for production API."""

from __future__ import annotations

import os

import psycopg2
import psycopg2.extras


def build_database_url() -> str:
    direct_url = os.getenv("DATABASE_URL", "").strip()
    if direct_url:
        return direct_url

    host = os.getenv("POSTGRES_HOST", "spainza-postgres").strip() or "spainza-postgres"
    port = os.getenv("POSTGRES_PORT", "5432").strip() or "5432"
    db = os.getenv("POSTGRES_DB", "spainza").strip() or "spainza"
    user = os.getenv("POSTGRES_USER", "spainza").strip() or "spainza"
    password = os.getenv("POSTGRES_PASSWORD", "").strip()
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


def get_connection():
    return psycopg2.connect(
        build_database_url(),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )
