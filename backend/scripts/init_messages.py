"""Initialize message tables."""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.message import Message

if __name__ == "__main__":
    print("Инициализация таблиц сообщений...")
    try:
        Message.create_table()
        print("[OK] Таблицы сообщений успешно созданы!")
    except Exception as e:
        print(f"[ERROR] Ошибка при создании таблиц: {e}")
        sys.exit(1)
