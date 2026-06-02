"""Upload project artifacts to VPS and rebuild spainza-site + spainza-backend.

Usage (PowerShell):
  $env:SPAINZA_SSH_PASSWORD='...'; python tools/remote_deploy.py

Or use SSH keys (ssh-agent / ~/.ssh/id_ed25519 / id_rsa).
"""
from __future__ import annotations

import getpass
import os
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
HOST = os.environ.get("SPAINZA_SSH_HOST", "185.73.126.68")
USER = os.environ.get("SPAINZA_SSH_USER", "root")
PASSWORD = os.environ.get("SPAINZA_SSH_PASSWORD", "")
REPO = os.environ.get("SPAINZA_REPO", "/opt/spainza")

ARCHIVE_TOP_LEVEL = (
    "frontend",
    "backend",
    "docker",
    "wsgi.py",
    "docker-compose.production.yml",
)


def run(client: paramiko.SSHClient, cmd: str, timeout: int = 900) -> int:
    print(f"\n$ {cmd}")
    _, stdout, stderr = client.exec_command(cmd, timeout=timeout, get_pty=True)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out.rstrip().encode("ascii", errors="replace").decode("ascii"))
    if err and code != 0:
        print(err.rstrip().encode("ascii", errors="replace").decode("ascii"), file=sys.stderr)
    return code


def should_skip(path: Path) -> bool:
    parts = path.parts
    if "__pycache__" in parts:
        return True
    if path.suffix in {".pyc", ".pyo"}:
        return True
    if path.name == "app.db" and "database" in parts:
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
                print(f"skip missing: {rel}")
                continue
            if src.is_file():
                tar.add(src, arcname=rel)
                continue
            for file_path in src.rglob("*"):
                if not file_path.is_file() or should_skip(file_path):
                    continue
                arcname = file_path.relative_to(ROOT).as_posix()
                tar.add(file_path, arcname=arcname)
    size_mb = archive_path.stat().st_size / (1024 * 1024)
    print(f"Archive: {archive_path} ({size_mb:.1f} MB)")
    return archive_path


def connect_ssh(client: paramiko.SSHClient) -> None:
    """Connect with password env, optional prompt, or SSH keys."""
    password = PASSWORD
    if not password and sys.stdin.isatty():
        try:
            password = getpass.getpass(f"SSH password for {USER}@{HOST}: ")
        except (EOFError, KeyboardInterrupt):
            password = ""

    connect_kwargs: dict = {
        "hostname": HOST,
        "username": USER,
        "timeout": 30,
        "allow_agent": True,
        "look_for_keys": True,
    }
    if password:
        connect_kwargs["password"] = password

    print(f"Connecting to {HOST}...")
    try:
        client.connect(**connect_kwargs)
    except paramiko.AuthenticationException:
        if password:
            raise
        print(
            "SSH authentication failed. Set SPAINZA_SSH_PASSWORD or configure keys.",
            file=sys.stderr,
        )
        raise


def main() -> int:
    archive_path = build_archive()

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_ssh(client)

    remote_tar = f"{REPO}/_deploy_payload.tar.gz"
    sftp = client.open_sftp()
    print(f"Uploading to {remote_tar}...")
    sftp.put(str(archive_path), remote_tar)
    sftp.close()
    archive_path.unlink(missing_ok=True)

    steps = [
        f"test -d {REPO} || mkdir -p {REPO}",
        f"cd {REPO} && tar -xzf _deploy_payload.tar.gz && rm -f _deploy_payload.tar.gz",
        (
            f"cd {REPO} && docker compose --env-file .env.production "
            f"-f docker-compose.production.yml build spainza-backend spainza-site"
        ),
        (
            f"cd {REPO} && docker compose --env-file .env.production "
            f"-f docker-compose.production.yml up -d --remove-orphans spainza-backend spainza-site"
        ),
        (
            f"cd {REPO} && docker compose --env-file .env.production "
            f"-f docker-compose.production.yml ps"
        ),
        (
            "curl -fsS -H 'Host: spainza.com' http://127.0.0.1/api/health "
            "&& echo && curl -fsS -o /dev/null -w '%{http_code}' -H 'Host: spainza.com' "
            "http://127.0.0.1/frontend/lk/configurator.html"
        ),
    ]

    for cmd in steps:
        code = run(client, cmd)
        if code != 0:
            print(f"Command failed ({code}): {cmd}", file=sys.stderr)
            client.close()
            return code

    client.close()
    print("\nDeployment finished.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
