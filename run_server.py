#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Скрипт для запуска локального Flask-сервера
Используйте этот файл для тестирования сайта с полным функционалом
включая авторизацию и личный кабинет
"""

import os
import sys
from pathlib import Path

# Fix encoding for Windows console
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Добавляем корневую директорию в путь
ROOT_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

# Добавляем директорию backend в путь для корректных импортов
BACKEND_DIR = ROOT_DIR / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Импортируем приложение Flask (app уже создан в backend/app.py)
from app import _run_dev_server
from config import Config, is_production_env

def main():
    """Запуск встроенного dev-сервера Flask (не для production)."""
    
    if is_production_env():
        print("APP_ENV=production: используйте WSGI, например:")
        print("  waitress-serve --listen=127.0.0.1:5000 wsgi:application")
        sys.exit(1)

    host = Config.FLASK_RUN_HOST
    port = Config.FLASK_RUN_PORT
    debug = Config.DEBUG
    reloader = debug and Config.FLASK_USE_RELOADER

    print("=" * 60)
    print("🚀 Запуск локального Flask-сервера")
    print("=" * 60)
    print()
    print("📍 Сервер будет доступен по адресу:")
    print(f"   http://localhost:{port}")
    print(f"   http://127.0.0.1:{port}")
    print()
    print("📄 Доступные страницы:")
    print("   • Главная:        http://localhost:5000/")
    print("   • Логин:          http://localhost:5000/login.html")
    print("   • Личный кабинет: http://localhost:5000/lk/dashboard.html")
    print()
    print("🔑 API эндпоинты:")
    print("   • POST /api/login         - Авторизация")
    print("   • POST /api/logout        - Выход")
    print("   • GET  /api/user          - Профиль пользователя")
    print("   • GET  /api/lk/*          - Эндпоинты личного кабинета")
    print()
    print(f"⚙️  Режим: Development (DEBUG={debug})")
    print(f"🔄 Автоперезагрузка: {'Включена' if reloader else 'Выключена'}")
    print("   Включить отладку: FLASK_DEBUG=1 в .env")
    print()
    print("💡 Для остановки сервера нажмите Ctrl+C")
    print("=" * 60)
    print()
    
    # Проверяем наличие базы данных
    db_path = ROOT_DIR / "database" / "app.db"
    if not db_path.exists():
        print("⚠️  ВНИМАНИЕ: База данных не найдена!")
        print(f"   Ожидается: {db_path}")
        print("   Создайте базу данных перед запуском сервера")
        print()
    
    # Запускаем сервер
    try:
        _run_dev_server()
    except KeyboardInterrupt:
        print("\n")
        print("=" * 60)
        print("🛑 Сервер остановлен")
        print("=" * 60)
    except Exception as e:
        print("\n")
        print("=" * 60)
        print(f"❌ Ошибка при запуске сервера: {e}")
        print("=" * 60)
        sys.exit(1)

if __name__ == "__main__":
    main()
