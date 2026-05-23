"""Test messaging functionality."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.message import Message
from models.user import User

def test_messaging():
    print("\n=== Тестирование системы сообщений ===\n")
    
    # Test 1: Create conversation
    print("1. Создание чата между пользователями 1 и 2...")
    try:
        conv_id = Message.get_or_create_conversation(1, 2)
        print(f"   [OK] Чат создан: {conv_id}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Test 2: Send message
    print("\n2. Отправка сообщения...")
    try:
        msg_id = Message.send_message(conv_id, 1, 2, "Привет! Это тестовое сообщение.")
        print(f"   [OK] Сообщение отправлено, ID: {msg_id}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Test 3: Get messages
    print("\n3. Получение сообщений...")
    try:
        messages = Message.get_messages(conv_id)
        print(f"   [OK] Получено сообщений: {len(messages)}")
        for msg in messages:
            print(f"       - От пользователя {msg['sender_id']}: {msg['message_text']}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Test 4: Get conversations for user
    print("\n4. Получение списка чатов для пользователя 1...")
    try:
        conversations = Message.get_conversations_for_user(1)
        print(f"   [OK] Найдено чатов: {len(conversations)}")
        for conv in conversations:
            print(f"       - Чат с: {conv['other_user_name']} (ID: {conv['other_user_id']})")
            print(f"         Непрочитанных: {conv['unread_count']}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Test 5: Mark as read
    print("\n5. Отметка сообщений как прочитанных...")
    try:
        Message.mark_as_read(conv_id, 2)
        unread = Message.get_unread_count(2)
        print(f"   [OK] Непрочитанных сообщений у пользователя 2: {unread}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Test 6: Send another message
    print("\n6. Отправка ответного сообщения...")
    try:
        msg_id = Message.send_message(conv_id, 2, 1, "Привет! Получил твое сообщение.")
        print(f"   [OK] Ответ отправлен, ID: {msg_id}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    # Test 7: Check unread count
    print("\n7. Проверка непрочитанных сообщений...")
    try:
        unread_user1 = Message.get_unread_count(1)
        unread_user2 = Message.get_unread_count(2)
        print(f"   [OK] Непрочитанных у пользователя 1: {unread_user1}")
        print(f"   [OK] Непрочитанных у пользователя 2: {unread_user2}")
    except Exception as e:
        print(f"   [ERROR] {e}")
        return False
    
    print("\n=== Все тесты пройдены успешно! ===\n")
    return True

if __name__ == "__main__":
    success = test_messaging()
    sys.exit(0 if success else 1)
