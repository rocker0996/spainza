"""Messaging routes."""
from flask import Blueprint, request, jsonify, g, send_file
from models.message import Message
from models.user import (
    User,
    get_role_permissions,
    get_user_by_id,
    get_internal_user_id_by_display_id,
    get_role_definition,
    may_initiate_chat_with_numeric_counterpart,
    normalize_public_display_id_value,
    normalize_role_key,
)
from config import Config
from services.file_service import FileService
from services.notification_service import EVENT_MESSAGE_RECEIVED, notify
from functools import wraps
import os

messages_bp = Blueprint('messages', __name__)


def _notify_message_received(
    db,
    *,
    sender_id: int,
    receiver_id: int,
    message_text: str | None,
    conversation_id: str,
    image_path: str | None = None,
    file_path: str | None = None,
) -> None:
    if sender_id == receiver_id:
        return
    sender = get_user_by_id(db, sender_id)
    if not sender:
        return
    sender_name = (sender["name"] or sender["email"] or "").strip() or "Spainza"
    notify(
        db,
        receiver_id,
        EVENT_MESSAGE_RECEIVED,
        {
            "sender_name": sender_name,
            "preview": (message_text or "").strip(),
            "has_attachment": bool(image_path or file_path),
            "conversation_id": conversation_id,
        },
    )


def _request_locale():
    body = request.get_json(silent=True) or {}
    raw = body.get("locale") or request.headers.get("X-User-Locale") or "ru"
    if isinstance(raw, str) and raw.strip().lower() == "en":
        return "en"
    return "ru"


def login_required(f):
    """Decorator to require login."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not hasattr(g, 'current_user_id') or g.current_user_id is None:
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function


def _viewer_may_access_message_row(message_row, viewer_user_id: int) -> bool:
    if not message_row:
        return False
    if viewer_user_id in (int(message_row["sender_id"]), int(message_row["receiver_id"])):
        return True

    viewer = get_user_by_id(g.db, int(viewer_user_id))
    if not viewer:
        return False
    permissions = set(get_role_permissions(normalize_role_key(viewer["role_key"] or "")))
    return "full_access" in permissions


def _serialize_message_for_api(message: dict) -> dict:
    payload = dict(message)
    message_id = int(payload.get("id", 0) or 0)
    image_path = payload.pop("image_path", None)
    file_path = payload.pop("file_path", None)

    body = payload.get("body_text") or payload.get("message_text")
    if body is None or str(body).strip() == "":
        body = ""
    payload["message_text"] = body
    payload["body_text"] = body

    payload["image_url"] = (
        f"/api/messages/{message_id}/image" if message_id > 0 and image_path else None
    )
    payload["file_url"] = (
        f"/api/messages/{message_id}/file" if message_id > 0 and file_path else None
    )
    return payload


def _serialize_messages_for_api(messages: list[dict]) -> list[dict]:
    return [_serialize_message_for_api(item) for item in (messages or [])]


def _public_user_search_payload(user_row) -> dict:
    role_key = normalize_role_key(user_row["role_key"] or "")
    role_data = get_role_definition(role_key)
    return {
        "display_id": (user_row["display_id"] or "").strip(),
        "name": (user_row["name"] or "").strip() or "Unknown",
        "avatar": (user_row["avatar"] or "").strip(),
        "role": {
            "key": role_data["key"],
            "name_ru": role_data["name_ru"],
        },
    }

@messages_bp.route('/api/conversations', methods=['GET'])
@login_required
def get_conversations():
    """Get all conversations for the current user."""
    try:
        user_id = g.current_user_id
        conversations = Message.get_conversations_for_user(user_id)
        
        # Get user info for each conversation
        for conv in conversations:
            other_user = User.get_by_id(conv['other_user_id'])
            if other_user:
                conv['other_user_email'] = other_user.get('email', '')
                conv['online'] = False  # Can be extended with real-time status
        
        return jsonify(conversations), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/api/conversations/<conversation_id>/messages', methods=['GET'])
@login_required
def get_conversation_messages(conversation_id):
    """Get messages for a specific conversation."""
    try:
        user_id = g.current_user_id
        
        # Verify user is part of this conversation
        parts = conversation_id.split('_')
        if len(parts) != 3 or parts[0] != 'conv':
            return jsonify({'error': 'Invalid conversation ID'}), 400
        
        user1_id = int(parts[1])
        user2_id = int(parts[2])
        
        if user_id not in [user1_id, user2_id]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        messages = Message.get_messages(conversation_id, viewer_user_id=user_id)

        # Mark messages as read
        Message.mark_as_read(conversation_id, user_id)
        
        return jsonify(_serialize_messages_for_api(messages)), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/api/conversations/create', methods=['POST'])
@login_required
def create_conversation():
    """Create or get a conversation with another user.

    По умолчанию собеседник задаётся публичным ``display_id`` (2 буквы + 4 цифры),
    чтобы нельзя было перебирать числовые id. Числовой ``user_id`` допускается только
    для поддержки и уже закреплённых в кейсе/списке менеджера контактов.
    """
    try:
        data = request.get_json(silent=True) or {}
        restore = bool(data.get('restore', False))

        display_raw = (data.get('display_id') or data.get('counterparty_display_id') or '').strip()
        normalized_display = (
            normalize_public_display_id_value(display_raw) if display_raw else None
        )

        other_user_id = None
        if normalized_display:
            candidate = get_internal_user_id_by_display_id(g.db, normalized_display)
            if candidate is None:
                return jsonify({'error': 'User not found'}), 404
            if candidate == g.current_user_id:
                return jsonify({'error': 'Cannot start a chat with yourself'}), 400
            other_user_id = candidate
        elif data.get('user_id') is not None and str(data.get('user_id')).strip() != '':
            try:
                numeric_other = int(data.get('user_id'))
            except (TypeError, ValueError):
                return jsonify({'error': 'Invalid user_id'}), 400
            if numeric_other < 1:
                return jsonify({'error': 'Invalid user_id'}), 400
            if numeric_other == g.current_user_id:
                return jsonify({'error': 'Cannot start a chat with yourself'}), 400
            if not may_initiate_chat_with_numeric_counterpart(
                g.db,
                int(g.current_user_id),
                int(numeric_other),
                support_user_id=Config.PORTAL_SUPPORT_USER_ID,
            ):
                return jsonify(
                    {
                        'error': (
                            'Чтобы написать пользователю, укажите его публичный номер '
                            '(2 латинские буквы и 4 цифры) в поле «Новый чат».'
                        ),
                    }
                ), 403
            other_user_id = numeric_other
        else:
            return jsonify({'error': 'display_id is required'}), 400

        user_id = g.current_user_id
        other_user = User.get_by_id(other_user_id)
        if not other_user:
            return jsonify({'error': 'User not found'}), 404

        conversation_id = Message.get_or_create_conversation(user_id, other_user_id, restore)

        # Get conversation details
        messages = Message.get_messages(conversation_id, viewer_user_id=user_id)

        return jsonify({
            'conversation_id': conversation_id,
            'other_user': {
                'id': other_user['id'],
                'name': other_user.get('full_name', 'Unknown'),
                'email': other_user.get('email', ''),
                'role': other_user.get('role', 'client')
            },
            'messages': _serialize_messages_for_api(messages)
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/api/conversations/<conversation_id>/messages', methods=['POST'])
@login_required
def send_message(conversation_id):
    """Send a message in a conversation."""
    try:
        user_id = g.current_user_id
        
        # Verify user is part of this conversation
        parts = conversation_id.split('_')
        if len(parts) != 3 or parts[0] != 'conv':
            return jsonify({'error': 'Invalid conversation ID'}), 400
        
        user1_id = int(parts[1])
        user2_id = int(parts[2])
        
        if user_id not in [user1_id, user2_id]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        # Determine receiver
        receiver_id = user2_id if user_id == user1_id else user1_id
        
        # Handle multipart form data (for images and files)
        if request.files or (
            request.content_type and "multipart/form-data" in request.content_type
        ):
            message_text = request.form.get('message_text')
            image_file = request.files.get('image')
            file_upload = request.files.get('file')
            
            image_path = None
            file_path = None
            file_name = None
            file_service = FileService()
            
            if image_file:
                # Save image
                image_path = file_service.save_message_image(image_file, user_id)
            
            if file_upload:
                # Save file
                file_path, file_name = file_service.save_message_file(file_upload, user_id)
            
            if not message_text and not image_path and not file_path:
                return jsonify({'error': 'Message must contain text, image, or file'}), 400

            reply_to_message_id = request.form.get('reply_to_message_id')
            if reply_to_message_id:
                try:
                    reply_to_message_id = int(reply_to_message_id)
                except (TypeError, ValueError):
                    return jsonify({'error': 'Invalid reply_to_message_id'}), 400
            
            message_id = Message.send_message(
                conversation_id,
                user_id,
                receiver_id,
                message_text,
                image_path,
                file_path,
                file_name,
                reply_to_message_id=reply_to_message_id,
            )
            _notify_message_received(
                g.db,
                sender_id=user_id,
                receiver_id=receiver_id,
                message_text=message_text,
                image_path=image_path,
                file_path=file_path,
                conversation_id=conversation_id,
            )
        else:
            # Handle JSON data
            data = request.get_json() or {}
            message_text = data.get('message_text')
            
            if not message_text:
                return jsonify({'error': 'message_text is required'}), 400

            reply_to_message_id = data.get('reply_to_message_id')
            if reply_to_message_id is not None:
                try:
                    reply_to_message_id = int(reply_to_message_id)
                except (TypeError, ValueError):
                    return jsonify({'error': 'Invalid reply_to_message_id'}), 400
            
            message_id = Message.send_message(
                conversation_id, 
                user_id, 
                receiver_id, 
                message_text,
                reply_to_message_id=reply_to_message_id,
            )
            _notify_message_received(
                g.db,
                sender_id=user_id,
                receiver_id=receiver_id,
                message_text=message_text,
                conversation_id=conversation_id,
            )
        
        return jsonify({
            'message_id': message_id,
            'success': True
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/api/messages/unread-count', methods=['GET'])
@login_required
def get_unread_count():
    """Get unread message count for current user."""
    try:
        user_id = g.current_user_id
        count = Message.get_unread_count(user_id)
        return jsonify({'unread_count': count}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/api/messages/<int:message_id>/image', methods=['GET'])
@login_required
def download_message_image(message_id):
    """Serve message image attachment by id (no file path leakage)."""
    message = Message.get_message_by_id(message_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    if not _viewer_may_access_message_row(message, int(g.current_user_id)):
        return jsonify({'error': 'Unauthorized'}), 403
    if message["deleted_by"] and int(message["deleted_by"]) == int(g.current_user_id):
        return jsonify({'error': 'Message deleted'}), 404
    image_path = message["image_path"]
    if not image_path:
        return jsonify({'error': 'Image not found'}), 404

    file_path = FileService().get_file_path(image_path)
    if not os.path.exists(file_path):
        return jsonify({'error': 'Image not found'}), 404
    return send_file(file_path, as_attachment=False)


@messages_bp.route('/api/messages/<int:message_id>/file', methods=['GET'])
@login_required
def download_message_file(message_id):
    """Serve message file attachment by id (no file path leakage)."""
    message = Message.get_message_by_id(message_id)
    if not message:
        return jsonify({'error': 'Message not found'}), 404
    if not _viewer_may_access_message_row(message, int(g.current_user_id)):
        return jsonify({'error': 'Unauthorized'}), 403
    if message["deleted_by"] and int(message["deleted_by"]) == int(g.current_user_id):
        return jsonify({'error': 'Message deleted'}), 404
    relative_path = message["file_path"]
    if not relative_path:
        return jsonify({'error': 'File not found'}), 404

    file_path = FileService().get_file_path(relative_path)
    if not os.path.exists(file_path):
        return jsonify({'error': 'File not found'}), 404

    download_name = (message["file_name"] or "").strip() or os.path.basename(file_path)
    return send_file(file_path, as_attachment=True, download_name=download_name)

@messages_bp.route('/api/conversations/<conversation_id>', methods=['DELETE'])
@login_required
def delete_conversation(conversation_id):
    """Delete conversation for current user."""
    try:
        user_id = g.current_user_id
        
        # Verify user is part of this conversation
        parts = conversation_id.split('_')
        if len(parts) != 3 or parts[0] != 'conv':
            return jsonify({'error': 'Invalid conversation ID'}), 400
        
        user1_id = int(parts[1])
        user2_id = int(parts[2])
        
        if user_id not in [user1_id, user2_id]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        Message.delete_conversation_for_user(
            conversation_id, user_id, locale=_request_locale()
        )
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Error deleting conversation: {e}")
        return jsonify({'error': str(e)}), 500

def _verify_conversation_participant(conversation_id, user_id):
    parts = conversation_id.split('_')
    if len(parts) != 3 or parts[0] != 'conv':
        return None, (jsonify({'error': 'Invalid conversation ID'}), 400)
    user1_id = int(parts[1])
    user2_id = int(parts[2])
    if user_id not in [user1_id, user2_id]:
        return None, (jsonify({'error': 'Unauthorized'}), 403)
    return (user1_id, user2_id), None


def _delete_single_message_handler(message_id, conversation_id=None):
    user_id = g.current_user_id
    row = Message.get_message_by_id(message_id)
    if not row:
        return jsonify({'error': 'Message not found'}), 404

    if conversation_id and row["conversation_id"] != conversation_id:
        return jsonify({'error': 'Message not in this conversation'}), 400

    _, err = _verify_conversation_participant(row["conversation_id"], user_id)
    if err:
        return err

    Message.delete_message_for_user(message_id, user_id)
    return jsonify({'success': True}), 200


@messages_bp.route(
    '/api/conversations/<conversation_id>/messages/<int:message_id>/delete',
    methods=['POST'],
)
@login_required
def delete_message_in_conversation(conversation_id, message_id):
    """Delete one message (preferred URL — same prefix as send/list messages)."""
    try:
        return _delete_single_message_handler(message_id, conversation_id=conversation_id)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error deleting message in conversation: {e}")
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/api/messages/<int:message_id>', methods=['DELETE'])
@login_required
def delete_single_message(message_id):
    """Delete one message for the current user (tombstone for the other participant)."""
    try:
        return _delete_single_message_handler(message_id)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error deleting message: {e}")
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/api/messages/<int:message_id>/delete', methods=['POST'])
@login_required
def delete_single_message_post(message_id):
    """POST fallback when DELETE is blocked by a proxy."""
    try:
        return _delete_single_message_handler(message_id)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        print(f"Error deleting message: {e}")
        return jsonify({'error': str(e)}), 500


@messages_bp.route('/api/conversations/<conversation_id>/clear', methods=['POST'])
@login_required
def clear_conversation_history(conversation_id):
    """Clear conversation history for current user."""
    try:
        user_id = g.current_user_id
        
        # Verify user is part of this conversation
        parts = conversation_id.split('_')
        if len(parts) != 3 or parts[0] != 'conv':
            return jsonify({'error': 'Invalid conversation ID'}), 400
        
        user1_id = int(parts[1])
        user2_id = int(parts[2])
        
        if user_id not in [user1_id, user2_id]:
            return jsonify({'error': 'Unauthorized'}), 403
        
        Message.clear_history_for_user(
            conversation_id, user_id, locale=_request_locale()
        )
        return jsonify({'success': True}), 200
    except Exception as e:
        print(f"Error clearing conversation history: {e}")
        return jsonify({'error': str(e)}), 500

@messages_bp.route('/api/users/search', methods=['GET'])
@login_required
def search_users():
    """Lookup a user by public display_id (2 letters + 4 digits) for starting a chat."""
    try:
        query = (request.args.get('q') or '').strip()
        if not query:
            return jsonify([]), 200

        normalized_display_id = normalize_public_display_id_value(query)
        if not normalized_display_id:
            return jsonify([]), 200

        user_id = get_internal_user_id_by_display_id(g.db, normalized_display_id)
        if user_id is None or int(user_id) == int(g.current_user_id):
            return jsonify([]), 200

        row = g.db.execute(
            """
            SELECT display_id, name, avatar, role_key
            FROM users
            WHERE id = ?
            LIMIT 1
            """,
            (int(user_id),),
        ).fetchone()
        if not row:
            return jsonify([]), 200

        return jsonify([_public_user_search_payload(row)]), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500
