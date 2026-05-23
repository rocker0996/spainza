#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

BRANCH="${1:-main}"
COMPOSE_FILE="docker-compose.production.yml"
ENV_FILE=".env.production"
ENV_EXAMPLE_FILE=".env.production.example"

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
  echo "Created $ENV_FILE from template. Fill real secrets before external access."
fi

echo "[3/6] Building and starting containers"
compose up -d --build --remove-orphans

echo "[4/6] Waiting for container health"
wait_for_service_health "spainza-postgres"
wait_for_service_health "spainza-backend"
wait_for_service_health "spainza-site"

echo "[5/6] Running runtime health checks"
compose exec -T spainza-postgres sh -lc 'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"'
compose exec -T spainza-backend python -c "import urllib.request; urllib.request.urlopen('http://spainza-backend:5000/api/health', timeout=5).read(); urllib.request.urlopen('http://spainza-site:80/', timeout=5).read()"

echo "[6/6] Deployment complete"
compose ps
