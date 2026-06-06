"""Bootstrap a fresh VPS for Spainza production (Docker, edge nginx, deploy).

Reads SSH credentials from .env.deploy.
Usage: python tools/bootstrap_server.py
"""
from __future__ import annotations

import os
import secrets
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.deploy_env import load_deploy_env

load_deploy_env()

HOST = os.environ.get("SPAINZA_SSH_HOST", "")
USER = os.environ.get("SPAINZA_SSH_USER", "root")
PASSWORD = os.environ.get("SPAINZA_SSH_PASSWORD", "")
REPO = os.environ.get("SPAINZA_REPO", "/opt/spainza")
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")

ARCHIVE_TOP_LEVEL = (
    "frontend",
    "backend",
    "shared",
    "docker",
    "tools",
    "wsgi.py",
    "run_telegram_worker.py",
    "requirements.txt",
    "docker-compose.production.yml",
    ".env.production.example",
    "deploy.sh",
    "index.html",
    "404.html",
    "contact.html",
    "gold.html",
    "nomad.html",
    "process.html",
    "privacy-policy.html",
    "servces.html",
)

EDGE_COMPOSE = """services:
  nginx:
    image: nginx:1.27-alpine
    container_name: boletus-edge-nginx
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./conf.d:/etc/nginx/conf.d:ro
      - ./ssl:/etc/nginx/ssl:ro
    networks:
      - edge

networks:
  edge:
    name: boletus_default
"""


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 1800) -> int:
    print(f"\n$ {cmd[:200]}{'...' if len(cmd) > 200 else ''}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out.rstrip().encode("ascii", errors="replace").decode("ascii"))
    if err and code != 0:
        print(err.rstrip()[:2000].encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
    return code


def should_skip(path: Path) -> bool:
    parts = path.parts
    if "__pycache__" in parts:
        return True
    if path.suffix in {".pyc", ".pyo"}:
        return True
    return False


def build_archive() -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tmp.close()
    archive_path = Path(tmp.name)
    with tarfile.open(archive_path, "w:gz") as tar:
        for rel in ARCHIVE_TOP_LEVEL:
            src = ROOT / rel
            if not src.exists():
                continue
            if src.is_file():
                tar.add(src, arcname=rel)
                continue
            for file_path in src.rglob("*"):
                if not file_path.is_file() or should_skip(file_path):
                    continue
                arcname = file_path.relative_to(ROOT).as_posix()
                tar.add(file_path, arcname=arcname)
    print(f"Archive: {archive_path} ({archive_path.stat().st_size / (1024 * 1024):.1f} MB)")
    return archive_path


def parse_local_env() -> dict[str, str]:
    data: dict[str, str] = {}
    for name in (".env", ".env.deploy"):
        path = ROOT / name
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def render_production_env(local: dict[str, str]) -> str:
    jwt = secrets.token_urlsafe(48)
    pg_pass = secrets.token_hex(32)
    admin_pass = secrets.token_urlsafe(24)
    token = local.get("TELEGRAM_BOT_TOKEN", "").strip()
    bot_user = local.get("TELEGRAM_BOT_USERNAME", "spainza_bot").strip().lstrip("@")
    smtp_pass = SMTP_PASSWORD or local.get("SMTP_PASSWORD", "").strip()

    lines = [
        "POSTGRES_DB=spainza",
        "POSTGRES_USER=spainza",
        f"POSTGRES_PASSWORD={pg_pass}",
        "POSTGRES_HOST=spainza-postgres",
        "POSTGRES_PORT=5432",
        f"DATABASE_URL=postgresql://spainza:{pg_pass}@spainza-postgres:5432/spainza",
        f"JWT_SECRET={jwt}",
        "COOKIE_SECURE=1",
        "BOOTSTRAP_ADMIN_EMAIL=admin@spainza.com",
        f"BOOTSTRAP_ADMIN_PASSWORD={admin_pass}",
        "BOOTSTRAP_ADMIN_NAME=Spainza Admin",
        "BOOTSTRAP_ADMIN_ROLE=management",
        "BOOTSTRAP_DEMO_EMAIL=",
        "BOOTSTRAP_DEMO_PASSWORD=",
        "BOOTSTRAP_DEMO_NAME=",
        "PUBLIC_BASE_URL=https://spainza.com",
        f"TELEGRAM_BOT_TOKEN={token}",
        f"TELEGRAM_BOT_USERNAME={bot_user}",
        "SMTP_HOST=smtp.spaceweb.ru",
        "SMTP_PORT=465",
        "SMTP_USERNAME=noreply@spainza.com",
        f"SMTP_PASSWORD={smtp_pass}",
        "SMTP_FROM_EMAIL=noreply@spainza.com",
        "SMTP_USE_SSL=1",
        "SMTP_USE_TLS=0",
        "PORTAL_SUPPORT_USER_ID=3",
    ]
    print("\nGenerated admin credentials (save these):")
    print("  email: admin@spainza.com")
    print(f"  password: {admin_pass}")
    return "\n".join(lines) + "\n"


def main() -> int:
    if not HOST or not PASSWORD:
        print("Set SPAINZA_SSH_HOST and SPAINZA_SSH_PASSWORD in .env.deploy", file=sys.stderr)
        return 1

    local = parse_local_env()
    if not local.get("TELEGRAM_BOT_TOKEN", "").strip():
        print("TELEGRAM_BOT_TOKEN missing in .env", file=sys.stderr)
        return 1

    archive_path = build_archive()
    prod_env = render_production_env(local)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)

    steps = [
        "export DEBIAN_FRONTEND=noninteractive",
        "apt-get update -qq",
        "apt-get install -y -qq curl ca-certificates gnupg openssl",
        "if ! command -v docker >/dev/null 2>&1; then curl -fsSL https://get.docker.com | sh; fi",
        "systemctl enable docker && systemctl start docker",
        "docker --version && docker compose version",
        "mkdir -p /opt/boletus/infra/edge/conf.d /opt/boletus/infra/edge/ssl",
        f"mkdir -p {REPO}",
    ]
    for cmd in steps:
        if run(client, cmd) != 0:
            return 1

    sftp = client.open_sftp()
    with sftp.file("/opt/boletus/infra/edge/docker-compose.yml", "w") as f:
        f.write(EDGE_COMPOSE)
    with sftp.file(f"{REPO}/.env.production", "w") as f:
        f.write(prod_env)
    remote_tar = f"{REPO}/_bootstrap_payload.tar.gz"
    print(f"Uploading project to {remote_tar}...")
    sftp.put(str(archive_path), remote_tar)
    sftp.close()
    archive_path.unlink(missing_ok=True)

    ssl_cmd = (
        "if [ ! -f /opt/boletus/infra/edge/ssl/origin.crt ]; then "
        "openssl req -x509 -nodes -days 3650 -newkey rsa:2048 "
        "-keyout /opt/boletus/infra/edge/ssl/origin.key "
        "-out /opt/boletus/infra/edge/ssl/origin.crt "
        "-subj '/CN=spainza.com/O=Spainza/C=FI'; "
        "chmod 600 /opt/boletus/infra/edge/ssl/origin.key; fi"
    )
    edge_steps = [
        ssl_cmd,
        f"chmod 600 {REPO}/.env.production",
        f"cd {REPO} && tar -xzf _bootstrap_payload.tar.gz && rm -f _bootstrap_payload.tar.gz",
        f"sed -i 's/\\r$//' {REPO}/tools/update_edge_nginx.sh {REPO}/docker/edge/spainza-site.conf",
        (
            f"cp {REPO}/docker/edge/spainza-site.conf /opt/boletus/infra/edge/conf.d/20-spainza.conf && "
            "sed -i 's|/etc/nginx/ssl/origin.crt|/etc/nginx/ssl/origin.crt|g' /opt/boletus/infra/edge/conf.d/20-spainza.conf"
        ),
        "cd /opt/boletus/infra/edge && docker compose up -d",
        (
            f"cd {REPO} && docker compose --env-file .env.production "
            f"-f docker-compose.production.yml build spainza-backend spainza-site spainza-telegram-worker"
        ),
        (
            f"cd {REPO} && docker compose --env-file .env.production "
            f"-f docker-compose.production.yml up -d --remove-orphans"
        ),
        "sleep 15",
        f"bash {REPO}/tools/update_edge_nginx.sh",
        (
            "curl -fsS -o /dev/null -w 'telegram=%{http_code}\n' --max-time 10 https://api.telegram.org"
        ),
        (
            "curl -fsS -H 'Host: spainza.com' http://127.0.0.1/api/health"
        ),
        (
            f"cd {REPO} && docker compose --env-file .env.production "
            f"-f docker-compose.production.yml ps"
        ),
        (
            f"cd {REPO} && docker compose --env-file .env.production "
            f"-f docker-compose.production.yml logs --tail=15 spainza-telegram-worker"
        ),
    ]
    for cmd in edge_steps:
        code = run(client, cmd, timeout=2400)
        if code != 0:
            print(f"Failed: {cmd[:120]}", file=sys.stderr)
            client.close()
            return code

    client.close()
    print("\nBootstrap complete.")
    print(f"Update Cloudflare DNS A record for spainza.com -> {HOST}")
    print("Cloudflare SSL mode: Full (self-signed origin cert) or paste Origin Certificate into /opt/boletus/infra/edge/ssl/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
