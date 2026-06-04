#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EDGE_CONF_DIR="${EDGE_CONF_DIR:-/opt/boletus/infra/edge/conf.d}"
EDGE_COMPOSE_FILE="${EDGE_COMPOSE_FILE:-/opt/boletus/infra/edge/docker-compose.yml}"
EDGE_CONTAINER="${EDGE_CONTAINER:-boletus-edge-nginx}"
DOMAIN="${DOMAIN:-spainza.com}"
WWW_DOMAIN="${WWW_DOMAIN:-www.${DOMAIN}}"
EDGE_SSL_CERT="${EDGE_SSL_CERT:-/etc/nginx/ssl/origin.crt}"
EDGE_SSL_KEY="${EDGE_SSL_KEY:-/etc/nginx/ssl/origin.key}"
TEMPLATE="${ROOT_DIR}/docker/edge/spainza-site.conf"
TARGET="${EDGE_CONF_DIR}/20-spainza.conf"

if [[ ! -f "$TEMPLATE" ]]; then
  echo "Missing nginx template: $TEMPLATE" >&2
  exit 1
fi
if [[ ! -d "$EDGE_CONF_DIR" ]]; then
  echo "Missing edge config directory: $EDGE_CONF_DIR" >&2
  exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -qx "$EDGE_CONTAINER"; then
  echo "Missing edge container: $EDGE_CONTAINER" >&2
  exit 1
fi

sed \
  -e "s/spainza.com www.spainza.com/${DOMAIN} ${WWW_DOMAIN}/" \
  -e "s|/etc/nginx/ssl/origin.crt|${EDGE_SSL_CERT}|" \
  -e "s|/etc/nginx/ssl/origin.key|${EDGE_SSL_KEY}|" \
  "$TEMPLATE" > "$TARGET"

docker compose -f "$EDGE_COMPOSE_FILE" exec -T nginx nginx -t
docker compose -f "$EDGE_COMPOSE_FILE" exec -T nginx nginx -s reload

curl -fsS -H "Host: ${DOMAIN}" http://127.0.0.1/api/health >/dev/null
echo "Edge nginx upload limit updated ($(grep client_max_body_size "$TARGET" | head -1))"
