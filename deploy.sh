#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:-spainza.com}"
WWW_DOMAIN="${WWW_DOMAIN:-www.${DOMAIN}}"
REPO_URL="${REPO_URL:-https://github.com/rocker0996/spainza.git}"
BRANCH="${BRANCH:-main}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/spainza}"
ENV_FILE="${ENV_FILE:-.env.production}"

EDGE_COMPOSE_FILE="${EDGE_COMPOSE_FILE:-/opt/boletus/infra/edge/docker-compose.yml}"
EDGE_CONF_DIR="${EDGE_CONF_DIR:-/opt/boletus/infra/edge/conf.d}"
EDGE_CONTAINER="${EDGE_CONTAINER:-boletus-edge-nginx}"
EDGE_NETWORK="${EDGE_NETWORK:-boletus_default}"
EDGE_SSL_CERT="${EDGE_SSL_CERT:-/etc/nginx/ssl/origin.crt}"
EDGE_SSL_KEY="${EDGE_SSL_KEY:-/etc/nginx/ssl/origin.key}"

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

need_root() {
  if [ "${EUID}" -ne 0 ]; then
    echo "Run as root: sudo bash deploy.sh" >&2
    exit 1
  fi
}

install_packages() {
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "This deploy script supports Ubuntu/Debian with apt-get." >&2
    exit 1
  fi

  log "Installing Docker and Git"
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y ca-certificates curl git
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" > /etc/apt/sources.list.d/docker.list
  apt-get update
  DEBIAN_FRONTEND=noninteractive apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

sync_repo() {
  log "Syncing ${REPO_URL}#${BRANCH} to ${DEPLOY_PATH}"
  mkdir -p "$(dirname "$DEPLOY_PATH")"

  if [ -d "${DEPLOY_PATH}/.git" ]; then
    git -C "$DEPLOY_PATH" fetch origin "$BRANCH"
    git -C "$DEPLOY_PATH" reset --hard "origin/${BRANCH}"
  else
    rm -rf "$DEPLOY_PATH"
    git clone --branch "$BRANCH" --single-branch "$REPO_URL" "$DEPLOY_PATH"
  fi

  cd "$DEPLOY_PATH"
}

ensure_env() {
  if [ -f "$ENV_FILE" ]; then
    chmod 600 "$ENV_FILE"
    return
  fi

  log "Creating ${DEPLOY_PATH}/${ENV_FILE}"
  cp .env.production.example "$ENV_FILE"

  admin_password="$(openssl rand -base64 24 | tr -d '\n')"
  sed -i \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(openssl rand -hex 32)|" \
    -e "s|^JWT_SECRET=.*|JWT_SECRET=$(openssl rand -hex 32)|" \
    -e "s|^SPAINZA_ADMIN_PASSWORD=.*|SPAINZA_ADMIN_PASSWORD=${admin_password}|" \
    "$ENV_FILE"
  chmod 600 "$ENV_FILE"

  log "Initial Spainza admin credentials"
  echo "Email: $(sed -n 's/^SPAINZA_ADMIN_EMAIL=//p' "$ENV_FILE")"
  echo "Password: ${admin_password}"
}

compose() {
  docker compose -f docker-compose.production.yml --env-file "$ENV_FILE" "$@"
}

start_stack() {
  log "Building and starting Spainza containers"
  compose up -d --build
  compose exec -T backend wget -qO- http://127.0.0.1:5000/api/health >/dev/null
  compose exec -T site wget -qO- http://127.0.0.1/health >/dev/null
}

connect_edge_network() {
  if ! docker network inspect "$EDGE_NETWORK" >/dev/null 2>&1; then
    log "Edge network ${EDGE_NETWORK} does not exist; skipping shared edge connection"
    return
  fi

  for container in spainza-site spainza-backend; do
    if ! docker inspect "$container" --format '{{json .NetworkSettings.Networks}}' | grep -q "\"${EDGE_NETWORK}\""; then
      docker network connect "$EDGE_NETWORK" "$container"
    fi
  done
}

configure_edge() {
  if [ ! -d "$EDGE_CONF_DIR" ] || ! docker ps --format '{{.Names}}' | grep -qx "$EDGE_CONTAINER"; then
    log "Shared edge nginx not found; Spainza stack is running but public proxy was not changed."
    return
  fi

  log "Configuring ${EDGE_CONTAINER} for ${DOMAIN}"
  cat > "${EDGE_CONF_DIR}/20-spainza.conf" <<NGINX
server {
  listen 80;
  listen 443 ssl;
  server_name ${DOMAIN} ${WWW_DOMAIN};

  ssl_certificate ${EDGE_SSL_CERT};
  ssl_certificate_key ${EDGE_SSL_KEY};

  location /health {
    access_log off;
    add_header Content-Type text/plain;
    return 200 "ok\\n";
  }

  location /api/ {
    proxy_pass http://spainza-backend:5000;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
  }

  location / {
    proxy_pass http://spainza-site:80;
    proxy_http_version 1.1;
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
  }
}
NGINX

  if [ -f "$EDGE_COMPOSE_FILE" ]; then
    docker compose -f "$EDGE_COMPOSE_FILE" exec -T nginx nginx -t
    docker compose -f "$EDGE_COMPOSE_FILE" exec -T nginx nginx -s reload
  else
    docker exec "$EDGE_CONTAINER" nginx -t
    docker exec "$EDGE_CONTAINER" nginx -s reload
  fi
}

print_summary() {
  log "Spainza deploy completed"
  compose ps
  echo "Repo: ${DEPLOY_PATH}"
  echo "URL: https://${DOMAIN}"
}

need_root
install_packages
sync_repo
ensure_env
start_stack
connect_edge_network
configure_edge
print_summary
