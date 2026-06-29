"""Documents routes for personal account."""

from flask import Blueprint, g, jsonify, request, send_file
from models.document import (
    get_documents_for_user, create_document, get_document_by_id,
    approve_document, reject_document, revoke_approval, delete_document,
    replace_document_file
)
from models.document_history import (
    add_document_history_entry,
    get_document_history_by_user
)
from models.user import (
    get_role_permissions,
    get_user_by_id,
    is_portal_staff_role,
    normalize_public_display_id_value,
    normalize_role_key,
    staff_may_access_target_user_workspace,
)
from models.case_data import (
    case_data_flag_is_true,
    find_case_document_request,
    get_case_data_by_user_id,
    set_case_document_request_fulfilled,
)
from services.case_template_apply import materialize_case_from_template_if_needed
from services.file_service import FileService
from services.notification_service import (
    EVENT_DOCUMENT_APPROVED,
    EVENT_DOCUMENT_REJECTED,
    notify,
)
import os
from utils.time import normalize_storage_datetime

documents_bp = Blueprint("documents", __name__)
file_service = FileService()


@documents_bp.get("/documents")
def list_documents():
    # Get current user
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    permissions = set(get_role_permissions(normalize_role_key(current_user["role_key"] or "")))
    target_user_id = request.args.get("userId", type=int)

    doc_self_permissions = {
        "full_access",
        "review_documents",
        "approve_documents",
        "upload_documents",
        "download_documents",
    }
    has_client_documents_access = bool(doc_self_permissions & permissions)

    if not target_user_id and is_portal_staff_role(current_user["role_key"] or ""):
        return jsonify(
            {"success": False, "error": "forbidden - staff cannot open own documents list"}
        ), 403

    client_display_id = None

    if not target_user_id:
        if not has_client_documents_access:
            return jsonify({"success": False, "error": "forbidden"}), 403
        user_id_to_fetch = g.current_user_id
        user_name = current_user["name"] if current_user["name"] else (current_user["email"] or "Пользователь")
    else:
        if not staff_may_access_target_user_workspace(g.db, g.current_user_id, target_user_id):
            return jsonify({"success": False, "error": "forbidden - cannot view other users' documents"}), 403
        workspace_doc_access = bool(doc_self_permissions & permissions) or (
            "view_assigned_clients" in permissions
        )
        if not workspace_doc_access:
            return jsonify({"success": False, "error": "forbidden - cannot view other users' documents"}), 403

        target_user = get_user_by_id(g.db, target_user_id)
        if not target_user:
            return jsonify({"success": False, "error": "target user not found"}), 404

        user_id_to_fetch = target_user_id
        user_name = target_user["name"] if target_user["name"] else (target_user["email"] or "Пользователь")
        client_display_id = normalize_public_display_id_value(target_user["display_id"] or "")

    materialize_case_from_template_if_needed(
        g.db, user_id_to_fetch, fallback_viewer_id=g.current_user_id
    )

    # Fetch uploaded documents (without seeding test data)
    rows = get_documents_for_user(g.db, user_id_to_fetch)

    documents = [
        {
            "id": row["id"],
            "title": row["title"] or "",
            "status": row["status"] or "pending",
            "icon": row["icon"] or "description",
            "file_type": row["file_type"] or "PDF",
            "file_size": row["file_size"] or "1.0 MB",
            "is_priority": bool(row["is_priority"]),
            "last_action_at": normalize_storage_datetime(row["last_action_at"]),
            "source": "uploaded",
            "rejection_comment": row["rejection_comment"] or "",
        }
        for row in rows
    ]

    # Fetch document requests from case_data
    case_data = get_case_data_by_user_id(g.db, user_id_to_fetch)
    document_requests = []
    
    if case_data and case_data.get("document_requests"):
        # Convert document requests to document format
        for idx, req in enumerate(case_data["document_requests"]):
            # Only include sent requests still waiting for client upload
            if case_data_flag_is_true(req.get("sent")) and not case_data_flag_is_true(
                req.get("fulfilled")
            ):
                document_requests.append({
                    "id": f"req_{req.get('id', idx)}",
                    "title": req.get("name", "Документ"),
                    "status": "pending",  # Requests are always pending until uploaded
                    "icon": "request_quote",
                    "file_type": "Запрос",
                    "file_size": "",
                    "is_priority": req.get("priority") == "urgent",
                    "last_action_at": normalize_storage_datetime(case_data.get("updated_at", "")),
                    "source": "request",
                    "description": req.get("description", ""),
                    "priority": req.get("priority", "normal")
                })

    # Build a fast lookup for uploaded documents by normalized title.
    # This lets one request card evolve through statuses instead of duplicating
    # with a separate uploaded card after file submission.
    def normalize_title(value):
        return (value or "").strip().lower()

    uploaded_by_title = {}
    for doc in documents:
        key = normalize_title(doc.get("title"))
        if key and key not in uploaded_by_title:
            # documents are already sorted by latest action, so keep first.
            uploaded_by_title[key] = doc

    merged_documents = []
    for request_doc in document_requests:
        request_key = normalize_title(request_doc.get("title"))
        matched_uploaded = uploaded_by_title.pop(request_key, None) if request_key else None

        if matched_uploaded:
            merged_doc = dict(matched_uploaded)
            merged_doc["request_id"] = request_doc["id"]
            merged_doc["request_description"] = request_doc.get("description", "")
            merged_doc["is_priority"] = bool(
                merged_doc.get("is_priority") or request_doc.get("is_priority")
            )
            merged_documents.append(merged_doc)
        else:
            merged_documents.append(request_doc)

    # Add uploaded docs that don't correspond to active requests.
    all_documents = merged_documents + list(uploaded_by_title.values())

    return jsonify({
        "success": True,
        "documents": all_documents,
        "user_name": user_name,
        "user_id": user_id_to_fetch,
        "client_display_id": client_display_id,
    }), 200


@documents_bp.post("/documents/upload")
def upload_document():
    """Upload a document file."""
    # Get current user
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    permissions = set(get_role_permissions(normalize_role_key(current_user["role_key"] or "")))
    can_upload_own = bool({"full_access", "upload_documents"} & permissions)
    can_upload_for_others = bool(
        {"full_access", "review_documents", "approve_documents"} & permissions
    )

    # Check if file is present
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "no file provided"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "no file selected"}), 400

    # Get optional parameters
    title = request.form.get('title', file.filename)
    is_priority = request.form.get('is_priority', '0')
    request_id = (request.form.get("request_id") or "").strip()  # req_<id> from documents UI
    raw_target_uid = request.form.get("user_id")
    try:
        parsed_target_uid = int(raw_target_uid) if raw_target_uid not in (None, "") else None
    except (TypeError, ValueError):
        parsed_target_uid = None

    if parsed_target_uid is not None:
        if not can_upload_for_others:
            return jsonify({"success": False, "error": "forbidden - no upload permission"}), 403
        if not staff_may_access_target_user_workspace(g.db, g.current_user_id, parsed_target_uid):
            return jsonify({"success": False, "error": "forbidden - no upload permission"}), 403
        document_user_id = parsed_target_uid
    else:
        if not can_upload_own:
            return jsonify({"success": False, "error": "forbidden - no upload permission"}), 403
        document_user_id = g.current_user_id

    case_data = get_case_data_by_user_id(g.db, document_user_id)
    matched_request = (
        find_case_document_request(case_data, request_id) if request_id else None
    )
    if matched_request:
        request_title = (matched_request.get("name") or "").strip()
        if request_title:
            title = request_title
        if matched_request.get("priority") == "urgent":
            is_priority = "1"

    try:
        # Save file using FileService
        file_path = file_service.save_document(file, document_user_id, 'general')
        
        # Get file info
        file_size_bytes = os.path.getsize(file_service.get_file_path(file_path))
        file_size_mb = file_size_bytes / (1024 * 1024)
        file_size = f"{file_size_mb:.1f} MB"
        
        # Get file extension
        file_ext = file.filename.rsplit('.', 1)[1].upper() if '.' in file.filename else 'FILE'
        
        # Create document record
        doc_id = create_document(
            g.db,
            document_user_id,
            title,
            file_path,
            file_ext,
            file_size,
            int(is_priority)
        )
        
        # Log the upload action
        add_document_history_entry(
            g.db,
            document_id=doc_id,
            user_id=document_user_id,
            editor_id=g.current_user_id,
            action="Документ загружен",
            details=f"Документ '{title}' был загружен"
        )

        if request_id and matched_request:
            set_case_document_request_fulfilled(
                g.db, document_user_id, request_id, fulfilled=True
            )
        
        return jsonify({
            "success": True,
            "document_id": doc_id,
            "message": "Document uploaded successfully"
        }), 201
        
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Upload failed: {str(e)}"}), 500


@documents_bp.get("/documents/<int:document_id>/download")
def download_document(document_id):
    """Download a document file."""
    # Get current user
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    # Get document
    document = get_document_by_id(g.db, document_id)
    if not document:
        return jsonify({"success": False, "error": "document not found"}), 404

    permissions = set(get_role_permissions(normalize_role_key(current_user["role_key"] or "")))
    doc_owner_id = int(document["user_id"])
    is_owner = doc_owner_id == g.current_user_id

    direct_download = bool(
        {"full_access", "download_documents", "review_documents", "approve_documents"} & permissions
    )

    if is_owner:
        if not direct_download:
            return jsonify({"success": False, "error": "forbidden - no download permission"}), 403
    else:
        if not staff_may_access_target_user_workspace(g.db, g.current_user_id, doc_owner_id):
            return jsonify({"success": False, "error": "forbidden - cannot access this document"}), 403
        if not direct_download:
            return jsonify({"success": False, "error": "forbidden - cannot access this document"}), 403
    
    # Check if file exists
    if not document["file_path"]:
        return jsonify({"success": False, "error": "no file associated with this document"}), 404
    
    file_path = file_service.get_file_path(document["file_path"])
    if not os.path.exists(file_path):
        return jsonify({"success": False, "error": "file not found on server"}), 404
    
    # Prepare download filename with extension
    title = document["title"]
    file_type = document["file_type"].lower()
    
    # Add extension if not present in title
    if not title.endswith(f'.{file_type}'):
        download_name = f"{title}.{file_type}"
    else:
        download_name = title
    
    # Send file
    return send_file(file_path, as_attachment=True, download_name=download_name)


@documents_bp.post("/documents/<int:document_id>/approve")
def approve_document_endpoint(document_id):
    """Approve a document."""
    # Get current user
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    # Check permissions
    permissions = set(get_role_permissions(normalize_role_key(current_user["role_key"] or "")))
    can_approve = bool({"full_access", "approve_documents", "review_documents"} & permissions)
    
    if not can_approve:
        return jsonify({"success": False, "error": "forbidden - no approval permission"}), 403

    # Get document
    document = get_document_by_id(g.db, document_id)
    if not document:
        return jsonify({"success": False, "error": "document not found"}), 404

    doc_owner = int(document["user_id"])
    if doc_owner != g.current_user_id and not staff_may_access_target_user_workspace(
        g.db, g.current_user_id, doc_owner
    ):
        return jsonify({"success": False, "error": "forbidden - no approval permission"}), 403
    
    # Approve document
    success = approve_document(g.db, document_id)
    
    if success:
        # Log the action
        add_document_history_entry(
            g.db,
            document_id=document_id,
            user_id=document["user_id"],
            editor_id=g.current_user_id,
            action="Документ одобрен",
            details=f"Документ '{document['title']}' был одобрен"
        )
        notify(
            g.db,
            int(document["user_id"]),
            EVENT_DOCUMENT_APPROVED,
            {"document_title": document["title"] or ""},
        )
        
        return jsonify({
            "success": True,
            "message": "Document approved successfully"
        }), 200
    else:
        return jsonify({"success": False, "error": "failed to approve document"}), 500


@documents_bp.post("/documents/<int:document_id>/reject")
def reject_document_endpoint(document_id):
    """Reject a document with a comment."""
    # Get current user
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    # Check permissions
    permissions = set(get_role_permissions(normalize_role_key(current_user["role_key"] or "")))
    can_reject = bool({"full_access", "approve_documents", "review_documents"} & permissions)
    
    if not can_reject:
        return jsonify({"success": False, "error": "forbidden - no rejection permission"}), 403

    # Get document
    document = get_document_by_id(g.db, document_id)
    if not document:
        return jsonify({"success": False, "error": "document not found"}), 404

    doc_owner = int(document["user_id"])
    if doc_owner != g.current_user_id and not staff_may_access_target_user_workspace(
        g.db, g.current_user_id, doc_owner
    ):
        return jsonify({"success": False, "error": "forbidden - no rejection permission"}), 403
    
    # Get rejection comment from request body
    data = request.get_json()
    comment = data.get("comment", "") if data else ""
    
    if not comment:
        return jsonify({"success": False, "error": "rejection comment is required"}), 400
    
    # Reject document
    success = reject_document(g.db, document_id, comment)
    
    if success:
        # Log the action
        add_document_history_entry(
            g.db,
            document_id=document_id,
            user_id=document["user_id"],
            editor_id=g.current_user_id,
            action="Документ отклонен",
            details=f"Документ '{document['title']}' был отклонен. Причина: {comment}"
        )
        notify(
            g.db,
            int(document["user_id"]),
            EVENT_DOCUMENT_REJECTED,
            {
                "document_title": document["title"] or "",
                "rejection_comment": comment,
            },
        )
        
        return jsonify({
            "success": True,
            "message": "Document rejected successfully"
        }), 200
    else:
        return jsonify({"success": False, "error": "failed to reject document"}), 500


@documents_bp.post("/documents/<int:document_id>/revoke")
def revoke_approval_endpoint(document_id):
    """Revoke approval of a document."""
    # Get current user
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    # Check permissions
    permissions = set(get_role_permissions(normalize_role_key(current_user["role_key"] or "")))
    can_revoke = bool({"full_access", "approve_documents", "review_documents"} & permissions)
    
    if not can_revoke:
        return jsonify({"success": False, "error": "forbidden - no revoke permission"}), 403

    # Get document
    document = get_document_by_id(g.db, document_id)
    if not document:
        return jsonify({"success": False, "error": "document not found"}), 404

    doc_owner = int(document["user_id"])
    if doc_owner != g.current_user_id and not staff_may_access_target_user_workspace(
        g.db, g.current_user_id, doc_owner
    ):
        return jsonify({"success": False, "error": "forbidden - no revoke permission"}), 403
    
    # Revoke approval
    success = revoke_approval(g.db, document_id)
    
    if success:
        # Log the action
        add_document_history_entry(
            g.db,
            document_id=document_id,
            user_id=document["user_id"],
            editor_id=g.current_user_id,
            action="Одобрение отозвано",
            details=f"Одобрение документа '{document['title']}' было отозвано"
        )
        
        return jsonify({
            "success": True,
            "message": "Approval revoked successfully"
        }), 200
    else:
        return jsonify({"success": False, "error": "failed to revoke approval"}), 500


@documents_bp.delete("/documents/<int:document_id>")
def delete_document_endpoint(document_id):
    """Delete a document."""
    # Get current user
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    # Check permissions
    permissions = set(get_role_permissions(normalize_role_key(current_user["role_key"] or "")))
    can_delete = bool({"full_access", "approve_documents", "review_documents"} & permissions)
    
    if not can_delete:
        return jsonify({"success": False, "error": "forbidden - no delete permission"}), 403

    # Get document
    document = get_document_by_id(g.db, document_id)
    if not document:
        return jsonify({"success": False, "error": "document not found"}), 404

    doc_owner = int(document["user_id"])
    if doc_owner != g.current_user_id and not staff_may_access_target_user_workspace(
        g.db, g.current_user_id, doc_owner
    ):
        return jsonify({"success": False, "error": "forbidden - no delete permission"}), 403
    
    # Log the action before deletion
    add_document_history_entry(
        g.db,
        document_id=document_id,
        user_id=document["user_id"],
        editor_id=g.current_user_id,
        action="Документ удален",
        details=f"Документ '{document['title']}' был удален"
    )
    
    # Delete file if exists
    if document["file_path"]:
        try:
            file_service.delete_file(document["file_path"])
        except Exception as e:
            print(f"Warning: Could not delete file: {e}")
    
    # Delete document record
    success = delete_document(g.db, document_id)
    
    if success:
        return jsonify({
            "success": True,
            "message": "Document deleted successfully"
        }), 200
    else:
        return jsonify({"success": False, "error": "failed to delete document"}), 500


@documents_bp.post("/documents/<int:document_id>/replace")
def replace_document_endpoint(document_id):
    """Replace file for an existing document."""
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    permissions = set(get_role_permissions(normalize_role_key(current_user["role_key"] or "")))
    can_moderate = bool({"full_access", "approve_documents", "review_documents"} & permissions)
    can_upload_own = bool({"full_access", "upload_documents"} & permissions)

    document = get_document_by_id(g.db, document_id)
    if not document:
        return jsonify({"success": False, "error": "document not found"}), 404

    doc_owner = int(document["user_id"])
    is_owner = doc_owner == g.current_user_id
    if can_moderate:
        if not is_owner and not staff_may_access_target_user_workspace(g.db, g.current_user_id, doc_owner):
            return jsonify({"success": False, "error": "forbidden - no replace permission"}), 403
    elif not (is_owner and can_upload_own):
        return jsonify({"success": False, "error": "forbidden - no replace permission"}), 403

    if "file" not in request.files:
        return jsonify({"success": False, "error": "no file provided"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"success": False, "error": "no file selected"}), 400

    new_title = request.form.get("title")

    try:
        new_file_path = file_service.save_document(file, document["user_id"], "general")

        file_size_bytes = os.path.getsize(file_service.get_file_path(new_file_path))
        file_size_mb = file_size_bytes / (1024 * 1024)
        file_size = f"{file_size_mb:.1f} MB"
        file_ext = file.filename.rsplit(".", 1)[1].upper() if "." in file.filename else "FILE"

        success = replace_document_file(
            g.db,
            document_id,
            new_file_path,
            file_ext,
            file_size,
            new_title,
        )
        if not success:
            return jsonify({"success": False, "error": "failed to replace document"}), 500

        old_file_path = document["file_path"]
        if old_file_path:
            try:
                file_service.delete_file(old_file_path)
            except Exception:
                pass

        add_document_history_entry(
            g.db,
            document_id=document_id,
            user_id=document["user_id"],
            editor_id=g.current_user_id,
            action="Файл документа заменен",
            details=f"Файл документа '{new_title or document['title']}' был заменен и отправлен на повторную проверку",
        )

        return jsonify({"success": True, "message": "Document replaced successfully"}), 200
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Replace failed: {str(e)}"}), 500


@documents_bp.get("/document-history/<int:user_id>")
def get_document_history_endpoint(user_id):
    """Get document history for a specific user."""
    # Get current user
    current_user = get_user_by_id(g.db, g.current_user_id)
    if not current_user:
        return jsonify({"success": False, "error": "user not found"}), 404

    permissions = set(get_role_permissions(normalize_role_key(current_user["role_key"] or "")))

    if user_id != g.current_user_id:
        if not staff_may_access_target_user_workspace(g.db, g.current_user_id, user_id):
            return jsonify({"success": False, "error": "forbidden - cannot view other users' history"}), 403
        doc_self_permissions = {
            "full_access",
            "review_documents",
            "approve_documents",
            "upload_documents",
            "download_documents",
        }
        if not (
            bool(doc_self_permissions & permissions) or "view_assigned_clients" in permissions
        ):
            return jsonify({"success": False, "error": "forbidden - cannot view other users' history"}), 403
    
    # Get history
    history = get_document_history_by_user(g.db, user_id, limit=50)
    
    return jsonify({
        "success": True,
        "history": history
    }), 200
