"""Patch production .env.production with Telegram settings from local .env.

SSH credentials: copy .env.deploy.example → .env.deploy (gitignored).

Usage:
  python tools/configure_production_telegram.py
"""
from __future__ import annotations

import getpass
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.deploy_env import load_deploy_env

load_deploy_env()

HOST = os.environ.get("SPAINZA_SSH_HOST", "185.73.126.68")
USER = os.environ.get("SPAINZA_SSH_USER", "root")
PASSWORD = os.environ.get("SPAINZA_SSH_PASSWORD", "")
REPO = os.environ.get("SPAINZA_REPO", "/opt/spainza")
ENV_FILE = f"{REPO}/.env.production"

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "https://spainza.com").strip()
TELEGRAM_BOT_USERNAME = os.environ.get("TELEGRAM_BOT_USERNAME", "spainza_bot").strip().lstrip("@")


def _parse_env_file(path: Path) -> dict[str, str]:
    data: dict[str, str] = {}
    if not path.is_file():
        return data
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip('"').strip("'")
    return data


def _render_env_file(data: dict[str, str], *, original_text: str) -> str:
    lines: list[str] = []
    seen: set[str] = set()
    for raw_line in original_text.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#") or "=" not in raw_line:
            lines.append(raw_line)
            continue
        key = raw_line.split("=", 1)[0].strip()
        if key in data:
            lines.append(f"{key}={data[key]}")
            seen.add(key)
        else:
            lines.append(raw_line)
    for key in ("PUBLIC_BASE_URL", "TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_USERNAME"):
        if key in data and key not in seen:
            lines.append(f"{key}={data[key]}")
    return "\n".join(lines).rstrip() + "\n"


def _connect(client: paramiko.SSHClient) -> None:
    password = PASSWORD
    if not password and sys.stdin.isatty():
        try:
            password = getpass.getpass(f"SSH password for {USER}@{HOST}: ")
        except (EOFError, KeyboardInterrupt):
            password = ""

    kwargs: dict = {
        "hostname": HOST,
        "username": USER,
        "timeout": 30,
        "allow_agent": True,
        "look_for_keys": True,
    }
    if password:
        kwargs["password"] = password

    print(f"Connecting to {HOST}...")
    client.connect(**kwargs)


def main() -> int:
    local = _parse_env_file(ROOT / ".env")
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or local.get("TELEGRAM_BOT_TOKEN", "").strip()
    username = (
        os.environ.get("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
        or local.get("TELEGRAM_BOT_USERNAME", "").strip().lstrip("@")
        or TELEGRAM_BOT_USERNAME
    )

    if not token:
        print("TELEGRAM_BOT_TOKEN not found. Set it in .env or TELEGRAM_BOT_TOKEN env.", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        _connect(client)
    except paramiko.AuthenticationException:
        print(
            "SSH authentication failed. Set SPAINZA_SSH_PASSWORD or configure SSH keys.",
            file=sys.stderr,
        )
        return 1

    sftp = client.open_sftp()
    try:
        with sftp.open(ENV_FILE, "r") as remote_file:
            original = remote_file.read().decode("utf-8")
    except FileNotFoundError:
        example = f"{REPO}/.env.production.example"
        print(f"{ENV_FILE} missing, creating from example...")
        stdin, stdout, stderr = client.exec_command(f"test -f {example} && cat {example} || echo ''")
        original = stdout.read().decode("utf-8")
        if not original.strip():
            original = "# Spainza production\n"

    merged = _parse_env_file(Path("_virtual"))
    for line in original.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            merged[key.strip()] = value.strip()

    merged["PUBLIC_BASE_URL"] = PUBLIC_BASE_URL
    merged["TELEGRAM_BOT_TOKEN"] = token
    merged["TELEGRAM_BOT_USERNAME"] = username

    rendered = _render_env_file(merged, original_text=original)
    with sftp.open(ENV_FILE, "w") as remote_file:
        remote_file.write(rendered.encode("utf-8"))
    sftp.close()

    client.exec_command(f"chmod 600 {ENV_FILE}")
    print(f"Updated {ENV_FILE}:")
    print(f"  PUBLIC_BASE_URL={PUBLIC_BASE_URL}")
    print(f"  TELEGRAM_BOT_USERNAME={username}")
    print("  TELEGRAM_BOT_TOKEN=***")

    restart_cmd = (
        f"cd {REPO} && docker compose --env-file .env.production "
        f"-f docker-compose.production.yml up -d spainza-backend spainza-telegram-worker"
    )
    print("\nRestarting backend + telegram worker...")
    _, stdout, stderr = client.exec_command(restart_cmd, timeout=300)
    code = stdout.channel.recv_exit_status()
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    if out:
        print(out.rstrip())
    if code != 0:
        print(err.rstrip(), file=sys.stderr)
        print("Env updated, but container restart failed. Run deploy manually.", file=sys.stderr)
        return code

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
