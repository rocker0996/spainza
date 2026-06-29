"""UTC datetime helpers for persisted event timestamps."""

from __future__ import annotations

from datetime import datetime, timezone


SQLITE_UTC_NOW = "strftime('%Y-%m-%dT%H:%M:%SZ', 'now')"


def utc_now() -> datetime:
    """Return timezone-aware current UTC time."""
    return datetime.now(timezone.utc)


def to_storage_datetime(value: datetime | None = None) -> str:
    """Serialize a datetime as an ISO-8601 UTC instant for SQLite text columns."""
    instant = value or utc_now()
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)
    return instant.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def normalize_storage_datetime(value: object) -> str:
    """Normalize legacy SQLite datetime strings to UTC ISO-8601 for API responses."""
    if value is None:
        return ""

    raw = str(value).strip()
    if not raw:
        return ""

    if raw.endswith("Z"):
        return raw

    candidate = raw
    if " " in candidate and "T" not in candidate:
        candidate = candidate.replace(" ", "T", 1)

    if candidate.endswith("+00:00"):
        return candidate.replace("+00:00", "Z")

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return raw

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return to_storage_datetime(parsed)


def parse_storage_datetime(value: object) -> datetime | None:
    """Parse stored UTC/legacy SQLite datetime strings into aware UTC datetimes."""
    normalized = normalize_storage_datetime(value)
    if not normalized:
        return None
    try:
        return datetime.fromisoformat(normalized.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None
