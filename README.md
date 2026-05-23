# Spainza

Production-ready setup for static frontend + API backend in Docker.

## Stack

- `spainza-site` - Nginx serving static files from `frontend/` and root HTML pages.
- `spainza-backend` - Flask API (`/api/*`) with JWT auth and PostgreSQL.
- `spainza-postgres` - PostgreSQL 16 with persistent Docker volume.
- Internal Docker network only (`spainza-internal`), no published ports in compose.

## Frontend Contract Covered

Backend provides minimum endpoints required by current frontend flow:

- `POST /api/login` -> `{ success, token, user }`
- `GET /api/lk/session` -> Bearer (or auth cookie) session check
- `GET /api/user` -> user profile, role, permissions, case status
- `GET /api/documents` -> `{ success, documents: [...] }`

Also available for deploy checks:

- `GET /api/health`
- `GET /api/health/db`

## Environment

1. Copy env template:

```bash
cp .env.production.example .env.production
```

2. Set real secrets in `.env.production`:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `DATABASE_URL` (optional override)
- `JWT_SECRET`
- `BOOTSTRAP_ADMIN_EMAIL`
- `BOOTSTRAP_ADMIN_PASSWORD`

Do not commit real secrets.

## Local Docker Run

`.env.production` for local dev is already filled (gitignored). See `LOCAL_SETUP.md`.

**Windows:**

```bat
start-local.bat
```

**Linux/macOS:**

```bash
docker compose --env-file .env.production -f docker-compose.production.yml -f docker-compose.local.yml up -d --build
```

Open: http://localhost:8080  
Login: см. `BOOTSTRAP_*` в локальном `.env.production` (файл не в git).

Stop:

```bash
docker compose --env-file .env.production -f docker-compose.production.yml -f docker-compose.local.yml down
```

## Production Deploy

Use idempotent script (safe for repeated deploys):

```bash
bash ./deploy.sh main
```

What `deploy.sh` does:

1. Fetches and hard-resets to `origin/<branch>`.
2. Creates `.env.production` from example if missing.
3. Runs `docker compose up -d --build --remove-orphans`.
4. Waits for `db`, `backend`, `site` health.
5. Executes runtime checks against DB and HTTP services.

## External Reverse Proxy

Your shared edge nginx on VPS should proxy:

- `/api/` -> `spainza-backend:5000`
- `/` -> `spainza-site:80`

Important:

- Do not install separate host nginx for Spainza.
- Do not publish backend/db ports to public interfaces.
