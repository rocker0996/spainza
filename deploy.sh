#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BRANCH="${1:-main}"
COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env.production"
ENV_EXAMPLE_FILE=".env.production.example"
EDGE_COMPOSE_FILE="${EDGE_COMPOSE_FILE:-/opt/boletus/infra/edge/docker-compose.yml}"
EDGE_CONF_DIR="${EDGE_CONF_DIR:-/opt/boletus/infra/edge/conf.d}"
EDGE_CONTAINER="${EDGE_CONTAINER:-boletus-edge-nginx}"
EDGE_NETWORK="${EDGE_NETWORK:-boletus_default}"
EDGE_SSL_CERT="${EDGE_SSL_CERT:-/etc/nginx/ssl/origin.crt}"
EDGE_SSL_KEY="${EDGE_SSL_KEY:-/etc/nginx/ssl/origin.key}"
DOMAIN="${DOMAIN:-spainza.com}"
WWW_DOMAIN="${WWW_DOMAIN:-www.${DOMAIN}}"

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

wait_for_service_health() {
  local service="$1"
  local retries="${2:-40}"

  local cid
  cid="$(compose ps -q "$service")"
  if [[ -z "$cid" ]]; then
    echo "Service $service is not running"
    return 1
  fi

  for ((i = 1; i <= retries; i++)); do
    local health
    health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$cid")"
    if [[ "$health" == "healthy" || "$health" == "running" ]]; then
      echo "Service $service is $health"
      return 0
    fi
    echo "Waiting for $service ($i/$retries), current=$health"
    sleep 3
  done

  echo "Service $service failed to become healthy"
  return 1
}

echo "[1/6] Syncing repository branch: $BRANCH"
git fetch --prune origin
current_branch="$(git rev-parse --abbrev-ref HEAD)"
if [[ "$current_branch" != "$BRANCH" ]]; then
  git checkout "$BRANCH"
fi
git reset --hard "origin/$BRANCH"

echo "[2/6] Ensuring production env file exists"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE_FILE" "$ENV_FILE"
  echo "Created $ENV_FILE from template."
fi
python3 - <<'PY'
from pathlib import Path
import os
import secrets

path = Path(".env.production")
data = {}
for line in path.read_text().splitlines():
    if not line or line.lstrip().startswith("#") or "=" not in line:
        continue
    key, value = line.split("=", 1)
    data[key] = value

def weak(value: str, *markers: str) -> bool:
    value = (value or "").strip()
    return not value or value.startswith("change_me") or value in markers

generated_admin_password = None

if weak(data.get("JWT_SECRET", "")):
    data["JWT_SECRET"] = secrets.token_urlsafe(48)

data.setdefault("COOKIE_SECURE", "1")

if weak(data.get("BOOTSTRAP_ADMIN_EMAIL", "")):
    data["BOOTSTRAP_ADMIN_EMAIL"] = data.get("SPAINZA_ADMIN_EMAIL") or "admin@spainza.com"
if weak(data.get("BOOTSTRAP_ADMIN_NAME", "")):
    data["BOOTSTRAP_ADMIN_NAME"] = data.get("SPAINZA_ADMIN_NAME") or "Spainza Admin"
if weak(data.get("BOOTSTRAP_ADMIN_ROLE", "")):
    data["BOOTSTRAP_ADMIN_ROLE"] = "management"
if weak(data.get("BOOTSTRAP_ADMIN_PASSWORD", "")):
    old_password = data.get("SPAINZA_ADMIN_PASSWORD", "")
    if weak(old_password):
        generated_admin_password = secrets.token_urlsafe(24)
        data["BOOTSTRAP_ADMIN_PASSWORD"] = generated_admin_password
    else:
        data["BOOTSTRAP_ADMIN_PASSWORD"] = old_password

data.setdefault("BOOTSTRAP_DEMO_EMAIL", "")
data.setdefault("BOOTSTRAP_DEMO_PASSWORD", "")
data.setdefault("BOOTSTRAP_DEMO_NAME", "")

data.setdefault("PUBLIC_BASE_URL", "https://spainza.com")
data.setdefault("TELEGRAM_BOT_USERNAME", "spainza_bot")
if not (data.get("TELEGRAM_BOT_TOKEN") or "").strip():
    token_from_env = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if token_from_env:
        data["TELEGRAM_BOT_TOKEN"] = token_from_env
    else:
        local_env = Path(".env")
        if local_env.is_file():
            for raw_line in local_env.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() == "TELEGRAM_BOT_TOKEN" and value.strip():
                    data["TELEGRAM_BOT_TOKEN"] = value.strip().strip('"').strip("'")
                    break

ordered = [
    "JWT_SECRET",
    "COOKIE_SECURE",
    "BOOTSTRAP_ADMIN_EMAIL",
    "BOOTSTRAP_ADMIN_PASSWORD",
    "BOOTSTRAP_ADMIN_NAME",
    "BOOTSTRAP_ADMIN_ROLE",
    "BOOTSTRAP_DEMO_EMAIL",
    "BOOTSTRAP_DEMO_PASSWORD",
    "BOOTSTRAP_DEMO_NAME",
    "PUBLIC_BASE_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BOT_USERNAME",
]
lines = [f"{key}={data[key]}" for key in ordered if key in data]
for key in sorted(set(data) - set(ordered)):
    lines.append(f"{key}={data[key]}")
path.write_text("\n".join(lines) + "\n")
os.chmod(path, 0o600)

if generated_admin_password:
    print("Initial admin credentials:")
    print(f"  email: {data['BOOTSTRAP_ADMIN_EMAIL']}")
    print(f"  password: {generated_admin_password}")
PY

echo "[3/6] Building and starting containers"
compose up -d --build --remove-orphans

echo "[4/6] Waiting for container health"
wait_for_service_health "spainza-backend"
wait_for_service_health "spainza-site"

echo "[5/6] Running runtime health checks"
compose exec -T spainza-backend python -c "import urllib.request; urllib.request.urlopen('http://spainza-backend:5000/api/health', timeout=5).read(); urllib.request.urlopen('http://spainza-site:80/', timeout=5).read()"

echo "[6/6] Configuring shared edge nginx"
if ! docker network inspect "$EDGE_NETWORK" >/dev/null 2>&1; then
  echo "Missing Docker network: $EDGE_NETWORK" >&2
  exit 1
fi

bash "$ROOT_DIR/tools/update_edge_nginx.sh"

curl -fsS -H "Host: ${DOMAIN}" http://127.0.0.1/ >/dev/null

echo "Deployment complete"
compose ps
