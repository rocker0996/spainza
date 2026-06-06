"""Patch production .env.production with SMTP settings for SpaceWeb mail.

Reads SMTP_PASSWORD from environment, .env.deploy, or local .env.
SSH credentials: copy .env.deploy.example → .env.deploy (gitignored).

Usage:
  python tools/configure_production_smtp.py
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

SMTP_DEFAULTS = {
    "SMTP_HOST": "smtp.spaceweb.ru",
    "SMTP_PORT": "465",
    "SMTP_USERNAME": "noreply@spainza.com",
    "SMTP_FROM_EMAIL": "noreply@spainza.com",
    "SMTP_USE_SSL": "1",
    "SMTP_USE_TLS": "0",
    "PUBLIC_BASE_URL": "https://spainza.com",
}


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
    smtp_keys = (
        "PUBLIC_BASE_URL",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM_EMAIL",
        "SMTP_USE_SSL",
        "SMTP_USE_TLS",
    )
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
    for key in smtp_keys:
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


def _resolve_smtp_password() -> str:
    local = _parse_env_file(ROOT / ".env")
    deploy = _parse_env_file(ROOT / ".env.deploy")
    for source in (
        os.environ.get("SMTP_PASSWORD", "").strip(),
        deploy.get("SMTP_PASSWORD", "").strip(),
        local.get("SMTP_PASSWORD", "").strip(),
    ):
        if source:
            return source
    if sys.stdin.isatty():
        try:
            entered = getpass.getpass("SMTP password for noreply@spainza.com: ")
            if entered.strip():
                return entered.strip()
        except (EOFError, KeyboardInterrupt):
            pass
    return ""


def main() -> int:
    smtp_password = _resolve_smtp_password()
    if not smtp_password:
        print(
            "SMTP_PASSWORD not found. Add it to .env.deploy or .env, then re-run:\n"
            "  SMTP_PASSWORD=your_mailbox_password python tools/configure_production_smtp.py",
            file=sys.stderr,
        )
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
        _, stdout, _stderr = client.exec_command(f"test -f {example} && cat {example} || echo ''")
        original = stdout.read().decode("utf-8")
        if not original.strip():
            original = "# Spainza production\n"

    merged = _parse_env_file(Path("_virtual"))
    for line in original.splitlines():
        if "=" in line and not line.strip().startswith("#"):
            key, value = line.split("=", 1)
            merged[key.strip()] = value.strip()

    merged.update(SMTP_DEFAULTS)
    merged["SMTP_PASSWORD"] = smtp_password

    rendered = _render_env_file(merged, original_text=original)
    with sftp.open(ENV_FILE, "w") as remote_file:
        remote_file.write(rendered.encode("utf-8"))
    sftp.close()

    client.exec_command(f"chmod 600 {ENV_FILE}")
    print(f"Updated {ENV_FILE}:")
    for key, value in SMTP_DEFAULTS.items():
        print(f"  {key}={value}")
    print("  SMTP_PASSWORD=***")

    restart_cmd = (
        f"cd {REPO} && docker compose --env-file .env.production "
        f"-f docker-compose.production.yml up -d --build spainza-backend"
    )
    print("\nRebuilding and restarting spainza-backend...")
    _, stdout, stderr = client.exec_command(restart_cmd, timeout=600)
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
