"""Message model."""
from datetime import datetime
from utils.db import get_db_connection


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
    def create_table():
        """Create messages table if it doesn't exist."""
        db = get_db_connection()
        db.execute('''
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                sender_id INTEGER NOT NULL,
                receiver_id INTEGER NOT NULL,
                message_text TEXT,
                image_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
                last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user1_deleted INTEGER DEFAULT 0,
                user2_deleted INTEGER DEFAULT 0,
                user1_history_cleared_at TIMESTAMP,
                user2_history_cleared_at TIMESTAMP,
                FOREIGN KEY (user1_id) REFERENCES users (id),
                FOREIGN KEY (user2_id) REFERENCES users (id),
                UNIQUE(user1_id, user2_id)
            )
        ''')
        Message._ensure_conversation_columns(db)
        Message._ensure_message_columns(db)
        db.commit()

    @staticmethod
    def _ensure_message_columns(db):
        """Add columns introduced after initial deploy (SQLite)."""
        cursor = db.execute("PRAGMA table_info(messages)")
        columns = {row[1] for row in cursor.fetchall()}
        if "file_path" not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN file_path TEXT")
        if "file_name" not in columns:
            db.execute("ALTER TABLE messages ADD COLUMN file_name TEXT")

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
                'last_message_at': row[6],
                'unread_count': row[7],
                'last_message': row[8],
                'last_message_time': row[9],
                'last_inbound_message': row[10],
                'last_inbound_message_time': row[11]
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
                'last_message_at': row[6],
                'hidden_for_subject': bool(row[7]),
                'last_message': row[8],
                'last_message_time': row[9],
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
            db.execute(
                'INSERT INTO conversations (id, user1_id, user2_id) VALUES (?, ?, ?)',
                (conversation_id, user1_id, user2_id)
            )
        elif restore:
            # Conversation exists and restore flag is True - restore it for the initiator
            Message.restore_conversation_for_user(conversation_id, initiator_id)
        
        db.commit()
        
        return conversation_id
    
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

        if cleared_at:
            cursor = db.execute(
                """
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
                    u.name as sender_name,
                    u.avatar as sender_avatar
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.conversation_id = ?
                  AND m.created_at >= ?
                ORDER BY m.created_at ASC
                LIMIT ?
                """,
                (conversation_id, cleared_at, limit),
            )
        else:
            cursor = db.execute(
                """
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
                    u.name as sender_name,
                    u.avatar as sender_avatar
                FROM messages m
                JOIN users u ON m.sender_id = u.id
                WHERE m.conversation_id = ?
                ORDER BY m.created_at ASC
                LIMIT ?
                """,
                (conversation_id, limit),
            )
        
        messages = []
        for row in cursor.fetchall():
            messages.append({
                'id': row[0],
                'sender_id': row[1],
                'receiver_id': row[2],
                'message_text': row[3],
                'image_path': row[4],
                'file_path': row[5],
                'file_name': row[6],
                'is_system_message': row[7],
                'created_at': row[8],
                'read_status': row[9],
                'sender_name': row[10],
                'sender_avatar': row[11]
            })
        
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
                file_name
            FROM messages
            WHERE id = ?
            LIMIT 1
            """,
            (message_id,),
        ).fetchone()
        return row
    
    @staticmethod
    def send_message(conversation_id, sender_id, receiver_id, message_text=None, image_path=None, file_path=None, file_name=None, is_system_message=False):
        """Send a message in a conversation."""
        if not message_text and not image_path and not file_path:
            raise ValueError("Message must contain text, image, or file")
        
        db = get_db_connection()
        Message._ensure_message_columns(db)
        
        # If receiver has deleted this conversation, restore it for them
        Message.restore_conversation_for_user(conversation_id, receiver_id)
        
        cursor = db.execute('''
            INSERT INTO messages (conversation_id, sender_id, receiver_id, message_text, image_path, file_path, file_name, is_system_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (conversation_id, sender_id, receiver_id, message_text, image_path, file_path, file_name, 1 if is_system_message else 0))
        
        # Update conversation last_message_at
        db.execute(
            'UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?',
            (conversation_id,)
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
            INSERT INTO messages (conversation_id, sender_id, receiver_id, message_text, is_system_message)
            VALUES (?, ?, ?, ?, 1)
        ''', (conversation_id, user_id, other_user_id, system_message))
        
        # Update last_message_at
        db.execute(
            'UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?',
            (conversation_id,)
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

        cleared_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
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
            "UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP WHERE id = ?",
            (conversation_id,),
        )

        db.commit()
        return True
