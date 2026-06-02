"""Apply manager/org case templates into case_data when fields are still empty (not manual)."""

from __future__ import annotations

import sqlite3
from typing import Any, Optional

from models.case_data import (
    case_data_flag_is_true,
    get_case_data_by_user_id,
    upsert_case_data,
)
from models.case_template import get_template_for_manager
from models.user import (
    GLOBAL_USER_ROLE_TEMPLATE_OWNER_ID,
    get_user_by_id,
    normalize_role_key,
)


def _row_str(row: Any, key: str, default: str = "") -> str:
    if row is None:
        return default
    try:
        val = row[key]
    except (KeyError, TypeError, IndexError):
        return default
    if val is None:
        return default
    return str(val)


def resolve_template_owner_id(
    connection: sqlite3.Connection,
    client_user_id: int,
    visa_type: str,
    *,
    fallback_viewer_id: Optional[int] = None,
) -> int:
    """Same rules as lk._resolve_template_owner_id_for_client (without Flask g)."""
    case = get_case_data_by_user_id(connection, client_user_id)
    target = get_user_by_id(connection, client_user_id)
    if case and case.get("manager_id"):
        return int(case["manager_id"])
    if target:
        client_role = normalize_role_key(_row_str(target, "role_key"))
        vt = str(visa_type or "").strip()
        if client_role == "user" and vt == "user":
            return int(GLOBAL_USER_ROLE_TEMPLATE_OWNER_ID)
    if fallback_viewer_id is not None:
        return int(fallback_viewer_id)
    return int(GLOBAL_USER_ROLE_TEMPLATE_OWNER_ID)


def _map_template_timeline_to_case(steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sorted_steps = sorted(steps, key=lambda s: int(s.get("order") or 0))
    out: list[dict[str, Any]] = []
    for i, s in enumerate(sorted_steps):
        duration = str(s.get("duration_label") or "").strip()
        desc = str(s.get("description") or "").strip()
        if duration:
            full_desc = f"Срок: {duration}\n\n{desc}" if desc else f"Срок: {duration}"
        else:
            full_desc = desc
        out.append(
            {
                "id": i + 1,
                "title": s.get("title") or f"Шаг {i + 1}",
                "description": full_desc,
                "status": "active" if i == 0 else "pending",
            }
        )
    return out


def _map_template_docs_to_case(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, it in enumerate(items):
        required = bool(it.get("required"))
        out.append(
            {
                "id": i + 1,
                "name": it.get("name") or "Документ",
                "description": str(it.get("description") or ""),
                "checked": required,
                "priority": it.get("priority") or "normal",
                "sent": required,
                "isDefault": True,
            }
        )
    return out


def materialize_case_from_template_if_needed(
    connection: sqlite3.Connection,
    client_user_id: int,
    *,
    fallback_viewer_id: Optional[int] = None,
) -> bool:
    """
    If timeline / document_requests are empty and the corresponding manual flag is off,
    copy from the resolved manager template and persist. Returns True if DB was updated.
    """
    target = get_user_by_id(connection, client_user_id)
    if not target:
        return False

    case = get_case_data_by_user_id(connection, client_user_id)
    visa_type = (
        str(case.get("visa_type") or "").strip()
        if case
        else normalize_role_key(_row_str(target, "role_key")) or "user"
    )
    if not visa_type:
        visa_type = "user"

    timeline_manual = bool(case and case.get("timeline_manual"))
    document_requests_manual = bool(case and case.get("document_requests_manual"))

    if timeline_manual and document_requests_manual:
        return False

    timeline = list(case["timeline"]) if case and case.get("timeline") else []
    docs = list(case["document_requests"]) if case and case.get("document_requests") else []

    if any(
        case_data_flag_is_true(item.get("sent"))
        for item in docs
        if isinstance(item, dict)
    ):
        return False

    need_timeline = not timeline_manual and len(timeline) == 0
    need_docs = not document_requests_manual and len(docs) == 0
    if not need_timeline and not need_docs:
        return False

    owner_id = resolve_template_owner_id(
        connection, client_user_id, visa_type, fallback_viewer_id=fallback_viewer_id
    )
    tpl = get_template_for_manager(connection, owner_id, visa_type)
    if not tpl:
        return False

    new_timeline = list(timeline)
    new_docs = list(docs)
    changed = False

    if need_timeline:
        raw = tpl.get("timeline") or []
        if isinstance(raw, list) and len(raw) > 0:
            new_timeline = _map_template_timeline_to_case(raw)
            changed = True

    if need_docs:
        raw_d = tpl.get("document_items") or []
        if isinstance(raw_d, list) and len(raw_d) > 0:
            new_docs = _map_template_docs_to_case(raw_d)
            changed = True

    if not changed:
        return False

    if case:
        return upsert_case_data(
            connection,
            client_user_id,
            visa_type,
            case.get("target_date"),
            case.get("country") or "",
            case.get("archive_file_path"),
            case.get("archive_file_name"),
            new_timeline,
            new_docs,
            referral_id=case.get("referral_id"),
            manager_id=case.get("manager_id"),
            timeline_manual=timeline_manual,
            document_requests_manual=document_requests_manual,
        )

    return upsert_case_data(
        connection,
        client_user_id,
        visa_type,
        None,
        "",
        None,
        None,
        new_timeline,
        new_docs,
        referral_id=None,
        manager_id=None,
        timeline_manual=False,
        document_requests_manual=False,
    )
