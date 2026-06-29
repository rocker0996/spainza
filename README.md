# Spainza Portal

Клиентский портал Spainza: сайт, личный кабинет, документы, сообщения и управление кейсами.

## Локальный запуск

1. Установите Python-зависимости:

```powershell
pip install -r requirements.txt
```

2. Установите frontend-зависимости:

```powershell
npm install
```

3. Запустите backend:

```powershell
python run_server.py
```

4. Откройте сайт:

```text
http://127.0.0.1:5000
```

## Полезные команды

Собрать CSS:

```powershell
npm.cmd run build:css
```

Запустить проверки:

```powershell
npm.cmd test
```

## Важные файлы

- `.env.example` - пример настроек для локального запуска.
- `.env.production.example` - пример настроек для сервера.
- `docker-compose.production.yml` - запуск на сервере.
- `backend/app.py` - главный Flask-сервер.
- `frontend/lk/` - страницы личного кабинета.

## Что не нужно добавлять в git

- `.env` и другие реальные файлы с паролями.
- `storage/` с загруженными файлами пользователей.
- `database/*.db` с локальной базой.
- `.vs/`, `.vscode/`, `.idea/` с настройками редакторов.
