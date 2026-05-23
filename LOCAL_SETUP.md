# Локальная настройка (готово)

Два варианта:

## A) Без Docker (рекомендуется на этой машине)

Полный backend (SQLite) + статика с одного Flask на **http://127.0.0.1:5000**:

```bat
start-dev.bat
```

Файл `.env` уже заполнен (gitignored).

## B) Docker (когда установлен Docker Desktop)

Postgres + prod API + static site + proxy на **http://localhost:8080**:

```bat
start-local.bat
```

Файл `.env.production` уже заполнен локальными значениями (gitignored).

## Быстрый старт Docker (Windows)

```bat
start-local.bat
```

Или PowerShell:

```powershell
.\start-local.ps1
```

Открыть в браузере: http://localhost:8080

## Учётные записи (только локально)

Задаются в `.env.production` (`BOOTSTRAP_ADMIN_*`, `BOOTSTRAP_DEMO_*`). Пароли в git не хранятся.

При первом старте Docker-backend пользователи создаются автоматически, если их ещё нет в БД.

## Файлы

| Файл | Назначение |
|------|------------|
| `.env.production` | Секреты для **локального** Docker (в git не попадает) |
| `.env.production.example` | Шаблон для продакшена на VPS |
| `docker-compose.production.yml` | Базовый compose (без портов наружу) |
| `docker-compose.local.yml` | Overlay: proxy `:8080`, сеть не internal |

## Остановка

```bash
docker compose --env-file .env.production -f docker-compose.production.yml -f docker-compose.local.yml down
```

## Для разработчика на проде

1. На VPS: `cp .env.production.example .env.production`
2. Заменить все `change_me_*` на сильные случайные значения
3. `COOKIE_SECURE=1` при HTTPS
4. `bash ./deploy.sh main` (без `docker-compose.local.yml`)
5. Edge nginx: `/api/` → `spainza-backend:5000`, `/` → `spainza-site:80`

Локальный `.env.production` на сервер **не копировать**.
