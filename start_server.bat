@echo off
chcp 65001 >nul
title Flask Server - Spain Project

echo.
echo ============================================================
echo 🚀 Запуск локального Flask-сервера
echo ============================================================
echo.
echo 📍 Сервер будет доступен по адресу:
echo    http://localhost:5000
echo.
echo 💡 Для остановки сервера закройте это окно или нажмите Ctrl+C
echo ============================================================
echo.

REM Проверяем наличие Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ОШИБКА: Python не найден!
    echo    Установите Python с https://www.python.org/
    echo.
    pause
    exit /b 1
)

REM Проверяем наличие виртуального окружения
if exist "venv\Scripts\activate.bat" (
    echo 🔧 Активация виртуального окружения...
    call venv\Scripts\activate.bat
    echo ✅ Виртуальное окружение активировано
    echo.
)

REM Проверяем установку Flask
python -c "import flask" >nul 2>&1
if errorlevel 1 (
    echo ⚠️  Flask не установлен. Устанавливаю зависимости...
    python -m pip install -r requirements.txt
    echo.
)

REM Запускаем сервер
echo 🚀 Запуск сервера...
echo.
python run_server.py

REM Если сервер остановлен
echo.
echo ============================================================
echo 🛑 Сервер остановлен
echo ============================================================
echo.
pause

