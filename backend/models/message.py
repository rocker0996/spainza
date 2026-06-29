"""Message model."""
from utils.db import get_db_connection
from utils.time import normalize_storage_datetime, to_storage_datetime


def _normalize_locale(locale):
    if isinstance(locale, str) and locale.strip().lower() == "en":
        return "en"
    return "ru"


def _default_actor_name(locale):
    return "User" if locale == "en" else "Пользователь"


def build_chat_system_message(action, user_name, locale="ru"):
    """System notification when a participant clears or deletes a chat."""
    locale = _normalize_locale(locale)
    name = (user_name or "").strip() or _default_actor_name(locale)
    if action == "clear":
        if locale == "en":
            return f"{name} cleared the message history"
        return f"{name} очистил(а) историю сообщений"
    if action == "delete":
        if locale == "en":
            return f"{name} deleted this chat"
        return f"{name} удалил(а) этот чат"
    return name

class Message:
    """Message model for chat system."""
    
    @staticmethod
    def create_table(connection=None):
        """Create messages table if it doesn't exist."""
        owns_connection = connection is None
        db = connection or get_db_connection()
        db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                message_text TEXT,
                image_path TEXT,
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                read_status INTEGER DEFAULT 0,
                is_system_message INTEGER DEFAULT 0,
                FOREIGN KEY (sender_id) REFERENCES users (id),
                FOREIGN KEY (receiver_id) REFERENCES users (id)
            )
        ''')
        
        db.execute('''
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user1_id INTEGER NOT NULL,
                user2_id INTEGER NOT NULL,
                last_message_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
                user1_deleted INTEGER DEFAULT 0,
                user2_deleted INTEGER DEFAULT 0,
                user1_history_cleared_at TEXT,
                user2_history_cleared_at TEXT,
                FOREIGN KEY (user1_id) REFERENCES users (id),
                FOREIGN KEY (user2_id) REFERENCES users (id),
                UNIQUE(user1_id, user2_id)
            )
        ''')
        Message._ensure_conversation_columns(db)
        Message._ensure_message_columns(db)
        db.commit()
        if owns_connection:
            db.close()

    @staticmethod
    def _ensure_message_columns(db):
        """Add columns introduced after initial deploy (SQLite)."""
        cursor = db.execute("PRAGMA table_info(messages)")
        columns = {row[1] for row in cursor.fetchall()}
        if "file_path" not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN file_path TEXT")
        if "file_name" not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN file_name TEXT")
        if "deleted_by" not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN deleted_by INTEGER")
        if "deleted_at" not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN deleted_at TIMESTAMP")
        if "reply_to_message_id" not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN reply_to_message_id INTEGER")
        if "deleted_content_text" not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN deleted_content_text TEXT")

    @staticmethod
    def _ensure_conversation_columns(db):
        """Add columns introduced after initial deploy (SQLite)."""
        cursor = db.execute("PRAGMA table_info(conversations)")
        columns = {row[1] for row in cursor.fetchall()}
        if "user1_history_cleared_at" not in columns:
            db.execute(
                "ALTER TABLE conversations ADD COLUMN user1_history_cleared_at TIMESTAMP"
            )
        if "user2_history_cleared_at" not in columns:
            db.execute(
                "ALTER TABLE conversations ADD COLUMN user2_history_cleared_at TIMESTAMP"
            )

    @staticmethod
    def _conversation_participant_ids(conversation_id):
        parts = (conversation_id or "").split("_")
        if len(parts) != 3 or parts[0] != "conv":
            return None
        try:
            return int(parts[1]), int(parts[2])
        except ValueError:
            return None

    @staticmethod
    def _history_cleared_at_for_user(db, conversation_id, user_id):
        row = db.execute(
            """
            SELECT user1_id, user2_id, user1_history_cleared_at, user2_history_cleared_at
            FROM conversations
            WHERE id = ?
            """,
            (conversation_id,),
        ).fetchone()
        if not row:
            return None
        if user_id == row["user1_id"]:
            return row["user1_history_cleared_at"]
        if user_id == row["user2_id"]:
            return row["user2_history_cleared_at"]
        return None
    
    @staticmethod
    def get_conversations_for_user(user_id):
        """Get all conversations for a user (excluding deleted ones)."""
        db = get_db_connection()
        cursor = db.execute('''
            SELECT
                c.id as conversation_id,
                CASE
                    WHEN c.user1_id = ? THEN c.user2_id
                    ELSE c.user1_id
                END as other_user_id,
                u.name as other_user_name,
                u.role_key as other_user_role,
                u.avatar as other_user_avatar,
                COALESCE(NULLIF(TRIM(u.display_id), ''), '') as other_user_display_id,
                c.last_message_at,
                COALESCE((SELECT COUNT(*) FROM messages
                 WHERE conversation_id = c.id
                 AND receiver_id = ?
                 AND read_status = 0), 0) as unread_count,
                (SELECT message_text FROM messages
                 WHERE conversation_id = c.id
                 AND ((sender_id = ? AND receiver_id != ?) OR (receiver_id = ? AND sender_id != ?))
                 ORDER BY created_at DESC LIMIT 1) as last_message,
                (SELECT created_at FROM messages
                 WHERE conversation_id = c.id
                 AND ((sender_id = ? AND receiver_id != ?) OR (receiver_id = ? AND sender_id != ?))
                 ORDER BY created_at DESC LIMIT 1) as last_message_time,
                (SELECT
                    CASE
                        WHEN TRIM(COALESCE(m.message_text, '')) != '' THEN m.message_text
                        WHEN TRIM(COALESCE(m.image_path, '')) != '' THEN 'Фото'
                        WHEN TRIM(COALESCE(m.file_path, '')) != '' THEN
                            COALESCE(NULLIF(TRIM(m.file_name), ''), 'Файл')
                        ELSE NULL
                    END
                 FROM messages m
                 WHERE m.conversation_id = c.id AND m.receiver_id = ?
                 ORDER BY m.created_at DESC LIMIT 1) as last_inbound_message,
                (SELECT m.created_at FROM messages m
                 WHERE m.conversation_id = c.id AND m.receiver_id = ?
                 ORDER BY m.created_at DESC LIMIT 1) as last_inbound_message_time
            FROM conversations c
            JOIN users u ON (
                CASE
                    WHEN c.user1_id = ? THEN c.user2_id
                    ELSE c.user1_id
                END = u.id
            )
            WHERE (c.user1_id = ? OR c.user2_id = ?)
            AND (
                (c.user1_id = ? AND c.user1_deleted = 0) OR
                (c.user2_id = ? AND c.user2_deleted = 0)
            )
            ORDER BY
                CASE WHEN c.last_message_at IS NULL THEN 1 ELSE 0 END,
                c.last_message_at DESC
        ''', (user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id))
        
        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                'id': row[0],
                'other_user_id': row[1],
                'other_user_name': row[2],
                'other_user_role': row[3],
                'other_user_avatar': row[4],
                'other_user_display_id': row[5] or None,
                'last_message_at': normalize_storage_datetime(row[6]),
                'unread_count': row[7],
                'last_message': row[8],
                'last_message_time': normalize_storage_datetime(row[9]),
                'last_inbound_message': row[10],
                'last_inbound_message_time': normalize_storage_datetime(row[11])
            })
        
        return conversations

    @staticmethod
    def get_conversations_for_user_audit(user_id):
        """All conversations for a user, including ones hidden by delete (for management audit)."""
        db = get_db_connection()
        cursor = db.execute(
            '''
            SELECT
                c.id as conversation_id,
                CASE
                    WHEN c.user1_id = ? THEN c.user2_id
                    ELSE c.user1_id
                END as other_user_id,
                u.name as other_user_name,
                u.role_key as other_user_role,
                u.avatar as other_user_avatar,
                COALESCE(NULLIF(TRIM(u.display_id), ''), '') as other_user_display_id,
                c.last_message_at,
                CASE
                    WHEN c.user1_id = ? THEN c.user1_deleted
                    ELSE c.user2_deleted
                END as hidden_for_subject,
                (SELECT message_text FROM messages
                 WHERE conversation_id = c.id
                 ORDER BY created_at DESC LIMIT 1) as last_message,
                (SELECT created_at FROM messages
                 WHERE conversation_id = c.id
                 ORDER BY created_at DESC LIMIT 1) as last_message_time
            FROM conversations c
            JOIN users u ON (
                CASE
                    WHEN c.user1_id = ? THEN c.user2_id
                    ELSE c.user1_id
                END = u.id
            )
            WHERE (c.user1_id = ? OR c.user2_id = ?)
            ORDER BY
                CASE WHEN c.last_message_at IS NULL THEN 1 ELSE 0 END,
                c.last_message_at DESC
            ''',
            (user_id, user_id, user_id, user_id, user_id),
        )

        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                'id': row[0],
                'other_user_id': row[1],
                'other_user_name': row[2],
                'other_user_role': row[3],
                'other_user_avatar': row[4],
                'other_user_display_id': row[5] or None,
                'last_message_at': normalize_storage_datetime(row[6]),
                'hidden_for_subject': bool(row[7]),
                'last_message': row[8],
                'last_message_time': normalize_storage_datetime(row[9]),
            })

        return conversations
    
    @staticmethod
    def get_or_create_conversation(user1_id, user2_id, restore=False):
        """Get or create a conversation between two users.
        
        Args:
            user1_id: First user ID
            user2_id: Second user ID
            restore: If True, restore deleted conversation for initiator. Default False.
        """
        db = get_db_connection()
        
        # Store original user IDs to know who initiated the request
        initiator_id = user1_id
        
        # Ensure consistent ordering (smaller ID first)
        if user1_id > user2_id:
            user1_id, user2_id = user2_id, user1_id
        
        conversation_id = f"conv_{user1_id}_{user2_id}"
        
        # Check if conversation exists
        cursor = db.execute(
            'SELECT id FROM conversations WHERE id = ?',
            (conversation_id,)
        )
        
        if cursor.fetchone() is None:
            # Create new conversation
            now_text = to_storage_datetime()
            db.execute(
                """
                INSERT INTO conversations (id, user1_id, user2_id, last_message_at, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (conversation_id, user1_id, user2_id, now_text, now_text),
            )
        elif restore:
            # Conversation exists and restore flag is True - restore it for the initiator
            Message.restore_conversation_for_user(conversation_id, initiator_id)
        
        db.commit()
        
        return conversation_id
    
    @staticmethod
    def _message_preview_text(row):
        """Short label for replies and list previews."""
        if not row:
            return ""
        text = (row.get("message_text") if isinstance(row, dict) else row["message_text"]) or ""
        text = str(text).strip()
        if text:
            return text[:200]
        image_path = row.get("image_path") if isinstance(row, dict) else row["image_path"]
        if image_path and str(image_path).strip():
            return "Фото"
        file_path = row.get("file_path") if isinstance(row, dict) else row["file_path"]
        if file_path and str(file_path).strip():
            file_name = row.get("file_name") if isinstance(row, dict) else row["file_name"]
            return (str(file_name).strip() if file_name else "") or "Файл"
        return ""

    @staticmethod
    def _build_reply_snapshot(db, reply_to_message_id):
        if not reply_to_message_id:
            return None
        row = db.execute(
            """
            SELECT
                m.id,
                m.sender_id,
                m.message_text,
                m.image_path,
                m.file_path,
                m.file_name,
                m.deleted_by,
                u.name AS sender_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            WHERE m.id = ?
            LIMIT 1
            """,
            (int(reply_to_message_id),),
        ).fetchone()
        if not row:
            return None
        deleted_by = row["deleted_by"]
        preview = None if deleted_by else Message._message_preview_text(row)
        return {
            "id": row["id"],
            "sender_id": row["sender_id"],
            "sender_name": row["sender_name"],
            "preview_text": preview,
            "is_deleted": bool(deleted_by),
        }

    @staticmethod
    def _row_to_message_dict(row, viewer_user_id=None):
        """Map DB row to API dict.

        Who deleted: message hidden for them only. Other participant keeps full content
        and gets is_deleted_by_peer for a UI hint.
        """
        deleted_by = row["deleted_by"] if "deleted_by" in row.keys() else None
        if deleted_by and viewer_user_id is not None and int(deleted_by) == int(viewer_user_id):
            return None

        reply_to = None
        reply_id = row["reply_to_message_id"] if "reply_to_message_id" in row.keys() else None
        if reply_id is not None:
            reply_sender_name = row["reply_sender_name"] if "reply_sender_name" in row.keys() else None
            reply_sender_id = row["reply_sender_id"] if "reply_sender_id" in row.keys() else None
            reply_deleted_by = row["reply_deleted_by"] if "reply_deleted_by" in row.keys() else None
            reply_ref = {
                "message_text": row["reply_message_text"]
                if "reply_message_text" in row.keys()
                else None,
                "image_path": row["reply_image_path"]
                if "reply_image_path" in row.keys()
                else None,
                "file_path": row["reply_file_path"]
                if "reply_file_path" in row.keys()
                else None,
                "file_name": row["reply_file_name"]
                if "reply_file_name" in row.keys()
                else None,
            }
            if reply_deleted_by:
                is_reply_deleted = True
                if viewer_user_id is not None and int(reply_deleted_by) == int(viewer_user_id):
                    reply_preview = None
                else:
                    reply_preview = Message._message_preview_text(reply_ref)
            else:
                reply_preview = Message._message_preview_text(reply_ref)
                is_reply_deleted = False
            reply_to = {
                "id": int(reply_id),
                "sender_id": reply_sender_id,
                "sender_name": reply_sender_name or "",
                "preview_text": (reply_preview or "")[:200] if reply_preview else "",
                "is_deleted": is_reply_deleted,
            }

        is_deleted_by_peer = bool(
            deleted_by
            and viewer_user_id is not None
            and int(deleted_by) != int(viewer_user_id)
        )
        deleted_by_name = None
        if is_deleted_by_peer and "deleted_by_name" in row.keys():
            deleted_by_name = row["deleted_by_name"]

        stored_text = row["message_text"] if "message_text" in row.keys() else None
        if (stored_text is None or str(stored_text).strip() == "") and "deleted_content_text" in row.keys():
            stored_text = row["deleted_content_text"]
        if stored_text is None:
            stored_text = ""

        return {
            "id": row["id"],
            "sender_id": row["sender_id"],
            "receiver_id": row["receiver_id"],
            "message_text": stored_text,
            "body_text": stored_text,
            "image_path": row["image_path"],
            "file_path": row["file_path"],
            "file_name": row["file_name"],
            "is_system_message": row["is_system_message"],
            "created_at": normalize_storage_datetime(row["created_at"]),
            "read_status": row["read_status"],
            "sender_name": row["sender_name"],
            "sender_avatar": row["sender_avatar"],
            "is_deleted_by_peer": is_deleted_by_peer,
            "deleted_by_user_id": deleted_by,
            "deleted_by_name": deleted_by_name,
            "reply_to_message_id": reply_id,
            "reply_to": reply_to,
        }

    @staticmethod
    def get_messages(conversation_id, limit=100, viewer_user_id=None, for_audit=False):
        """Get messages for a conversation.

        When viewer_user_id is set, hide messages before that user's history clear
        (soft delete). Audit passes for_audit=True to return the full thread.
        """
        db = get_db_connection()
        Message._ensure_conversation_columns(db)

        cleared_at = None
        if viewer_user_id is not None and not for_audit:
            cleared_at = Message._history_cleared_at_for_user(
                db, conversation_id, int(viewer_user_id)
            )

        select_sql = """
            SELECT
                m.id,
                m.sender_id,
                m.receiver_id,
                m.message_text,
                m.image_path,
                m.file_path,
                m.file_name,
                m.is_system_message,
                m.created_at,
                m.read_status,
                m.deleted_by,
                m.deleted_at,
                m.deleted_content_text,
                m.reply_to_message_id,
                u.name AS sender_name,
                u.avatar AS sender_avatar,
                du.name AS deleted_by_name,
                rm.sender_id AS reply_sender_id,
                rm.message_text AS reply_message_text,
                rm.image_path AS reply_image_path,
                rm.file_path AS reply_file_path,
                rm.file_name AS reply_file_name,
                rm.deleted_by AS reply_deleted_by,
                ru.name AS reply_sender_name
            FROM messages m
            JOIN users u ON m.sender_id = u.id
            LEFT JOIN users du ON m.deleted_by = du.id
            LEFT JOIN messages rm ON m.reply_to_message_id = rm.id
            LEFT JOIN users ru ON rm.sender_id = ru.id
            WHERE m.conversation_id = ?
        """

        if cleared_at:
            cursor = db.execute(
                select_sql
                + """
                  AND m.created_at >= ?
                ORDER BY m.created_at ASC
                LIMIT ?
                """,
                (conversation_id, cleared_at, limit),
            )
        else:
            cursor = db.execute(
                select_sql
                + """
                ORDER BY m.created_at ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            )

        messages = []
        for row in cursor.fetchall():
            if for_audit:
                messages.append({
                    "id": row["id"],
                    "sender_id": row["sender_id"],
                    "receiver_id": row["receiver_id"],
                    "message_text": row["message_text"],
                    "image_path": row["image_path"],
                    "file_path": row["file_path"],
                    "file_name": row["file_name"],
                    "is_system_message": row["is_system_message"],
                    "created_at": normalize_storage_datetime(row["created_at"]),
                    "read_status": row["read_status"],
                    "sender_name": row["sender_name"],
                    "sender_avatar": row["sender_avatar"],
                    "deleted_by": row["deleted_by"],
                    "reply_to_message_id": row["reply_to_message_id"],
                })
                continue

            item = Message._row_to_message_dict(row, viewer_user_id=viewer_user_id)
            if item is not None:
                messages.append(item)

        return messages

    @staticmethod
    def get_messages_for_audit(conversation_id, limit=500):
        """Full message history for management audit (ignores clear/delete UI state)."""
        return Message.get_messages(
            conversation_id, limit=limit, for_audit=True
        )

    @staticmethod
    def get_message_by_id(message_id):
        """Get one message row by id for attachment access checks."""
        db = get_db_connection()
        row = db.execute(
            """
            SELECT
                id,
                conversation_id,
                sender_id,
                receiver_id,
                image_path,
                file_path,
                file_name,
                deleted_by
            FROM messages
            WHERE id = ?
            LIMIT 1
            """,
            (message_id,),
        ).fetchone()
        return row
    
    @staticmethod
    def send_message(
        conversation_id,
        sender_id,
        receiver_id,
        message_text=None,
        image_path=None,
        file_path=None,
        file_name=None,
        is_system_message=False,
        reply_to_message_id=None,
    ):
        """Send a message in a conversation."""
        if not message_text and not image_path and not file_path:
            raise ValueError("Message must contain text, image, or file")
        
        db = get_db_connection()
        Message._ensure_message_columns(db)

        if reply_to_message_id is not None:
            reply_to_message_id = int(reply_to_message_id)
            ref = db.execute(
                """
                SELECT id, conversation_id, is_system_message
                FROM messages
                WHERE id = ?
                LIMIT 1
                """,
                (reply_to_message_id,),
            ).fetchone()
            if not ref:
                raise ValueError("Reply message not found")
            if ref["conversation_id"] != conversation_id:
                raise ValueError("Reply message is not in this conversation")
            if ref["is_system_message"]:
                raise ValueError("Cannot reply to a system message")
        
        # If receiver has deleted this conversation, restore it for them
        Message.restore_conversation_for_user(conversation_id, receiver_id)
        
        now_text = to_storage_datetime()
        cursor = db.execute(
            """
            INSERT INTO messages (
                conversation_id, sender_id, receiver_id, message_text,
                image_path, file_path, file_name, is_system_message, reply_to_message_id,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                sender_id,
                receiver_id,
                message_text,
                image_path,
                file_path,
                file_name,
                1 if is_system_message else 0,
                reply_to_message_id,
                now_text,
            ),
        )
        
        # Update conversation last_message_at
        db.execute(
            'UPDATE conversations SET last_message_at = ? WHERE id = ?',
            (now_text, conversation_id)
        )
        
        db.commit()
        
        return cursor.lastrowid
    
    @staticmethod
    def restore_conversation_for_user(conversation_id, user_id):
        """Restore a deleted conversation for a user (reset deletion flag)."""
        db = get_db_connection()
        
        # Get conversation details
        parts = conversation_id.split('_')
        if len(parts) != 3:
            return  # Invalid conversation ID, skip silently
        
        user1_id = int(parts[1])
        user2_id = int(parts[2])
        
        # Determine which deletion flag to reset
        if user_id == user1_id:
            delete_field = 'user1_deleted'
        elif user_id == user2_id:
            delete_field = 'user2_deleted'
        else:
            return  # User not part of conversation, skip silently
        
        # Reset deletion flag
        db.execute(
            f'UPDATE conversations SET {delete_field} = 0 WHERE id = ?',
            (conversation_id,)
        )
        db.commit()
    
    @staticmethod
    def mark_as_read(conversation_id, user_id):
        """Mark all messages in a conversation as read for a user."""
        db = get_db_connection()
        db.execute('''
            UPDATE messages 
            SET read_status = 1 
            WHERE conversation_id = ? AND receiver_id = ? AND read_status = 0
        ''', (conversation_id, user_id))
        db.commit()
    
    @staticmethod
    def get_unread_count(user_id):
        """Get total unread message count for a user."""
        db = get_db_connection()
        cursor = db.execute('''
            SELECT COUNT(*) 
            FROM messages 
            WHERE receiver_id = ? AND read_status = 0
        ''', (user_id,))
        
        return cursor.fetchone()[0]
    
    @staticmethod
    def delete_conversation_for_user(conversation_id, user_id, locale="ru"):
        """Mark conversation as deleted for a specific user and send system message."""
        locale = _normalize_locale(locale)
        db = get_db_connection()
        
        # Get conversation details
        parts = conversation_id.split('_')
        if len(parts) != 3:
            raise ValueError("Invalid conversation ID")
        
        user1_id = int(parts[1])
        user2_id = int(parts[2])
        
        # Determine which user is deleting and who is the other user
        if user_id == user1_id:
            delete_field = 'user1_deleted'
            other_user_id = user2_id
        elif user_id == user2_id:
            delete_field = 'user2_deleted'
            other_user_id = user1_id
        else:
            raise ValueError("User not part of this conversation")
        
        # Mark as deleted for this user
        db.execute(
            f'UPDATE conversations SET {delete_field} = 1 WHERE id = ?',
            (conversation_id,)
        )
        
        # Send system message to other user
        cursor = db.execute(
            'SELECT name FROM users WHERE id = ?',
            (user_id,)
        )
        user_row = cursor.fetchone()
        user_name = user_row[0] if user_row else _default_actor_name(locale)

        system_message = build_chat_system_message("delete", user_name, locale)
        
        db.execute('''
            INSERT INTO messages (
                conversation_id, sender_id, receiver_id, message_text, is_system_message, created_at
            )
            VALUES (?, ?, ?, ?, 1, ?)
        ''', (conversation_id, user_id, other_user_id, system_message, to_storage_datetime()))
        
        # Update last_message_at
        db.execute(
            'UPDATE conversations SET last_message_at = ? WHERE id = ?',
            (to_storage_datetime(), conversation_id)
        )
        
        db.commit()
        return True
    
    @staticmethod
    def clear_history_for_user(conversation_id, user_id, locale="ru"):
        """Hide prior messages for one participant; full history remains in DB for audit."""
        locale = _normalize_locale(locale)
        db = get_db_connection()
        Message._ensure_conversation_columns(db)

        parts = conversation_id.split('_')
        if len(parts) != 3:
            raise ValueError("Invalid conversation ID")

        user1_id = int(parts[1])
        user2_id = int(parts[2])

        if user_id == user1_id:
            cleared_field = "user1_history_cleared_at"
            other_user_id = user2_id
        elif user_id == user2_id:
            cleared_field = "user2_history_cleared_at"
            other_user_id = user1_id
        else:
            raise ValueError("User not part of this conversation")

        cleared_at = to_storage_datetime()
        db.execute(
            f"UPDATE conversations SET {cleared_field} = ? WHERE id = ?",
            (cleared_at, conversation_id),
        )

        cursor = db.execute("SELECT name FROM users WHERE id = ?", (user_id,))
        user_row = cursor.fetchone()
        user_name = user_row[0] if user_row else _default_actor_name(locale)

        system_message = build_chat_system_message("clear", user_name, locale)

        db.execute(
            """
            INSERT INTO messages (
                conversation_id, sender_id, receiver_id, message_text, is_system_message, created_at
            )
            VALUES (?, ?, ?, ?, 1, ?)
            """,
            (conversation_id, user_id, other_user_id, system_message, cleared_at),
        )

        db.execute(
            "UPDATE conversations SET last_message_at = ? WHERE id = ?",
            (cleared_at, conversation_id),
        )

        db.commit()
        return True

    @staticmethod
    def delete_message_for_user(message_id, user_id):
        """Soft-delete one message: hidden for deleter, tombstone for the other participant."""
        db = get_db_connection()
        Message._ensure_message_columns(db)

        row = db.execute(
            """
            SELECT id, conversation_id, sender_id, receiver_id, is_system_message, deleted_by
            FROM messages
            WHERE id = ?
            LIMIT 1
            """,
            (int(message_id),),
        ).fetchone()
        if not row:
            raise ValueError("Message not found")
        if row["is_system_message"]:
            raise ValueError("Cannot delete system message")
        if row["deleted_by"]:
            raise ValueError("Message already deleted")

        participants = Message._conversation_participant_ids(row["conversation_id"])
        if not participants or int(user_id) not in participants:
            raise ValueError("User not part of this conversation")

        deleted_at = to_storage_datetime()
        db.execute(
            """
            UPDATE messages
            SET deleted_by = ?,
                deleted_at = ?,
                deleted_content_text = COALESCE(NULLIF(TRIM(message_text), ''), deleted_content_text, message_text)
            WHERE id = ?
            """,
            (int(user_id), deleted_at, int(message_id)),
        )
        db.commit()
        return True
