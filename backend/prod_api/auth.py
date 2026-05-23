"""JWT helpers for production API."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from flask import Request


def jwt_secret() -> str:
    secret = (os.getenv("JWT_SECRET", "") or os.getenv("SECRET_KEY", "")).strip()
    if not secret:
        raise RuntimeError("JWT_SECRET (or SECRET_KEY) must be set")
    return secret


def issue_token(user_id: int) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": int(user_id),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=7)).timestamp()),
    }
    return jwt.encode(payload, jwt_secret(), algorithm="HS256")


def _extract_bearer_token(request: Request) -> str:
    header = (request.headers.get("Authorization") or "").strip()
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return ""


def read_token_from_request(request: Request) -> str:
    bearer = _extract_bearer_token(request)
    if bearer:
        return bearer
    return (request.cookies.get("access_token") or "").strip()


def decode_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None
    try:
        payload = jwt.decode(token, jwt_secret(), algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
    return payload if isinstance(payload, dict) else None
