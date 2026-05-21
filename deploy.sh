#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${DOMAIN:-spainza.com}"
WWW_DOMAIN="${WWW_DOMAIN:-www.${DOMAIN}}"
REPO_URL="${REPO_URL:-https://github.com/rocker0996/spainza.git}"
BRANCH="${BRANCH:-main}"
APP_ROOT="${APP_ROOT:-/var/www/${DOMAIN}}"
RELEASE_DIR="${RELEASE_DIR:-${APP_ROOT}/current}"
NGINX_SITE="${NGINX_SITE:-/etc/nginx/sites-available/${DOMAIN}}"
ENABLE_SSL="${ENABLE_SSL:-1}"
CERTBOT_EMAIL="${CERTBOT_EMAIL:-}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root: sudo env DOMAIN=${DOMAIN} bash deploy.sh"
  exit 1
fi

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

install_packages() {
  if command -v apt-get >/dev/null 2>&1; then
    log "Installing system packages"
    apt-get update
    DEBIAN_FRONTEND=noninteractive apt-get install -y git nginx certbot python3-certbot-nginx curl ca-certificates
  else
    echo "This script currently supports Debian/Ubuntu servers with apt-get."
    exit 1
  fi
}

deploy_repository() {
  log "Deploying ${REPO_URL}#${BRANCH} to ${RELEASE_DIR}"
  mkdir -p "${APP_ROOT}"

  if [[ -d "${RELEASE_DIR}/.git" ]]; then
    git -C "${RELEASE_DIR}" fetch origin "${BRANCH}"
    git -C "${RELEASE_DIR}" reset --hard "origin/${BRANCH}"
  else
    rm -rf "${RELEASE_DIR}"
    git clone --branch "${BRANCH}" --single-branch "${REPO_URL}" "${RELEASE_DIR}"
  fi

  if [[ ! -f "${RELEASE_DIR}/frontend/index.html" ]]; then
    echo "Expected static site entrypoint not found: ${RELEASE_DIR}/frontend/index.html"
    exit 1
  fi

  chown -R www-data:www-data "${APP_ROOT}"
}

configure_nginx() {
  log "Configuring nginx for ${DOMAIN}"
  cat > "${NGINX_SITE}" <<NGINX
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN} ${WWW_DOMAIN};

    root ${RELEASE_DIR}/frontend;
    index index.html;

    access_log /var/log/nginx/${DOMAIN}.access.log;
    error_log /var/log/nginx/${DOMAIN}.error.log;

    location / {
        try_files \$uri \$uri/ \$uri.html /index.html;
    }

    location ~* \.(?:css|js|mjs|jpg|jpeg|gif|png|svg|webp|ico|woff2?)$ {
        try_files \$uri =404;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
NGINX

  ln -sfn "${NGINX_SITE}" "/etc/nginx/sites-enabled/${DOMAIN}"
  rm -f /etc/nginx/sites-enabled/default
  nginx -t
  systemctl enable --now nginx
  systemctl reload nginx || systemctl restart nginx
}

configure_ssl() {
  if [[ "${ENABLE_SSL}" != "1" ]]; then
    log "Skipping SSL because ENABLE_SSL=${ENABLE_SSL}"
    return
  fi

  log "Requesting Let's Encrypt certificate for ${DOMAIN} and ${WWW_DOMAIN}"
  local email_args
  if [[ -n "${CERTBOT_EMAIL}" ]]; then
    email_args=(--email "${CERTBOT_EMAIL}")
  else
    email_args=(--register-unsafely-without-email)
  fi

  certbot --nginx \
    --non-interactive \
    --agree-tos \
    "${email_args[@]}" \
    -d "${DOMAIN}" \
    -d "${WWW_DOMAIN}" \
    --redirect
}

print_summary() {
  log "Deployment finished"
  echo "Site root: ${RELEASE_DIR}/frontend"
  echo "Nginx site: ${NGINX_SITE}"
  echo "URL: https://${DOMAIN}"
}

install_packages
deploy_repository
configure_nginx
configure_ssl
print_summary
