"""Read model used by Telegram client-assistant screens."""

from __future__ import annotations

from dataclasses import dataclass, field
import sqlite3
from typing import Literal, Optional

from models.case_data import case_data_flag_is_true, get_case_data_by_user_id
from models.document import get_documents_for_user
from services.notification_service import lk_url


TaskKind = Literal["upload", "reupload", "client_action"]


@dataclass(frozen=True)
class ClientTask:
    kind: TaskKind
    title: str
    due_at: Optional[str]
    detail: Optional[str]
    url: str


@dataclass(frozen=True)
class DocumentItem:
    title: str
    status: str
    detail: Optional[str]
    updated_at: Optional[str]


@dataclass(frozen=True)
class DocumentSummary:
    pending_upload: int = 0
    in_review: int = 0
    approved: int = 0
    needs_fix: int = 0
    items: tuple[DocumentItem, ...] = ()


@dataclass(frozen=True)
class CaseStep:
    title: str
    status: str
    description: Optional[str] = None


@dataclass(frozen=True)
class CaseSummary:
    steps: tuple[CaseStep, ...] = ()
    active_title: Optional[str] = None
    active_description: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass(frozen=True)
class ClientSummary:
    tasks: list[ClientTask] = field(default_factory=list)
    documents: DocumentSummary = field(default_factory=DocumentSummary)
    case: CaseSummary = field(default_factory=CaseSummary)


def _request_title(request: dict) -> str:
    return str(request.get("name") or request.get("title") or "Документ").strip() or "Документ"


def load_client_summary(connection: sqlite3.Connection, user_id: int) -> ClientSummary:
    case_data = get_case_data_by_user_id(connection, user_id)
    rows = get_documents_for_user(connection, user_id)

    tasks: list[ClientTask] = []
    items: list[DocumentItem] = []
    counts = {"pending_upload": 0, "in_review": 0, "approved": 0, "needs_fix": 0}

    for row in rows:
        status = str(row["status"] or "pending").strip().lower()
        detail = str(row["rejection_comment"] or "").strip() or None
        items.append(
            DocumentItem(
                title=str(row["title"] or "—").strip() or "—",
                status=status,
                detail=detail,
                updated_at=str(row["last_action_at"] or "").strip() or None,
            )
        )
        if status == "rejected":
            counts["needs_fix"] += 1
            tasks.append(
                ClientTask(
                    kind="reupload",
                    title=str(row["title"] or "—").strip() or "—",
                    due_at=None,
                    detail=detail,
                    url=lk_url("/frontend/lk/documents.html"),
                )
            )
        elif status == "approved":
            counts["approved"] += 1
        else:
            counts["in_review"] += 1

    requests = (case_data or {}).get("document_requests") or []
    for request in requests:
        if not isinstance(request, dict):
            continue
        if not case_data_flag_is_true(request.get("sent")) or case_data_flag_is_true(
            request.get("fulfilled")
        ):
            continue
        counts["pending_upload"] += 1
        tasks.append(
            ClientTask(
                kind="upload",
                title=_request_title(request),
                due_at=str(request.get("deadline") or request.get("due_date") or "").strip() or None,
                detail=("urgent" if str(request.get("priority") or "").lower() == "urgent" else None),
                url=lk_url("/frontend/lk/documents.html"),
            )
        )

    severity = {"reupload": 0, "upload": 1, "client_action": 2}
    tasks.sort(key=lambda task: (task.due_at is None, task.due_at or "", severity[task.kind], task.title.casefold()))

    steps: list[CaseStep] = []
    active_title: Optional[str] = None
    active_description: Optional[str] = None
    for raw in (case_data or {}).get("timeline") or []:
        if not isinstance(raw, dict):
            continue
        status = str(raw.get("status") or "pending").strip().lower()
        title = str(raw.get("title") or "—").strip() or "—"
        description = str(raw.get("description") or raw.get("details") or "").strip() or None
        steps.append(CaseStep(title=title, status=status, description=description))
        if status == "active" and active_title is None:
            active_title = title
            active_description = description

    return ClientSummary(
        tasks=tasks,
        documents=DocumentSummary(items=tuple(items), **counts),
        case=CaseSummary(
            steps=tuple(steps),
            active_title=active_title,
            active_description=active_description,
            updated_at=(case_data or {}).get("updated_at") or None,
        ),
    )
