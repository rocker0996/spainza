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

log() {
  printf '\n[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"
}

deploy_with_docker_proxy() {
  local repo_dir="${APP_DIR:-${HOME}/spainza}"
  local deploy_dir="${DEPLOY_DIR:-${HOME}/spainza-deploy}"
  local docker_network="${DOCKER_NETWORK:-boletus_default}"
  local proxy_conf_dir="${PROXY_CONF_DIR:-/opt/boletus/infra/nginx/conf.d}"
  local proxy_container="${PROXY_CONTAINER:-boletus-nginx}"
  local site_container="${SITE_CONTAINER:-spainza-site}"

  if [[ -d "${repo_dir}/.git" ]]; then
    log "Updating ${repo_dir}"
    git -C "${repo_dir}" fetch origin "${BRANCH}"
    git -C "${repo_dir}" reset --hard "origin/${BRANCH}"
  elif [[ -d ".git" && -f "frontend/index.html" ]]; then
    repo_dir="$(pwd)"
    log "Using current repository at ${repo_dir}"
  else
    log "Cloning ${REPO_URL}#${BRANCH} to ${repo_dir}"
    rm -rf "${repo_dir}"
    git clone --branch "${BRANCH}" --single-branch "${REPO_URL}" "${repo_dir}"
  fi

  if [[ ! -f "${repo_dir}/frontend/index.html" ]]; then
    echo "Expected static site entrypoint not found: ${repo_dir}/frontend/index.html"
    exit 1
  fi

  mkdir -p "${deploy_dir}"
  cat > "${deploy_dir}/default.conf" <<'NGINX_STATIC'
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    location /health {
        access_log off;
        return 200 "ok\n";
        add_header Content-Type text/plain;
    }

    location / {
        try_files $uri $uri/ $uri.html /index.html;
    }

    location ~* \.(?:css|js|mjs|jpg|jpeg|gif|png|svg|webp|ico|woff2?)$ {
        try_files $uri =404;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }
}
NGINX_STATIC

  log "Starting ${site_container} on Docker network ${docker_network}"
  docker rm -f "${site_container}" >/dev/null 2>&1 || true
  docker run -d \
    --name "${site_container}" \
    --restart unless-stopped \
    --network "${docker_network}" \
    -v "${repo_dir}/frontend:/usr/share/nginx/html:ro" \
    -v "${deploy_dir}/default.conf:/etc/nginx/conf.d/default.conf:ro" \
    nginx:alpine >/dev/null

  if [[ -w "${proxy_conf_dir}" ]] && docker ps --format '{{.Names}}' | grep -qx "${proxy_container}"; then
    log "Configuring ${proxy_container} virtual host for ${DOMAIN}"
    cat > "${proxy_conf_dir}/10-${DOMAIN}.conf" <<NGINX_PROXY
server {
  listen 80;
  server_name ${DOMAIN} ${WWW_DOMAIN};

  location /health {
    access_log off;
    return 200 "ok\\n";
    add_header Content-Type text/plain;
  }

  location / {
    proxy_pass http://${site_container}:80;
    include /etc/nginx/snippets/proxy-headers.conf;
  }
}
NGINX_PROXY

    docker exec "${proxy_container}" nginx -t
    docker exec "${proxy_container}" nginx -s reload
  else
    log "Proxy config was not changed; set PROXY_CONF_DIR/PROXY_CONTAINER or add a vhost manually."
  fi

  log "Docker deployment finished"
  echo "Site container: ${site_container}"
  echo "Site root: ${repo_dir}/frontend"
  echo "URL: https://${DOMAIN}"
}

if [[ "${EUID}" -ne 0 ]]; then
  if command -v docker >/dev/null 2>&1 && docker info >/dev/null 2>&1; then
    deploy_with_docker_proxy
    exit 0
  else
    echo "Run as root: sudo env DOMAIN=${DOMAIN} bash deploy.sh"
    exit 1
  fi
fi

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
