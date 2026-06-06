"""Create or update a user on production via SSH + docker exec.

Usage:
  python tools/create_production_user.py --email user@example.com --password '...' \\
    --name "Name" --role support --id 3
"""
from __future__ import annotations

import argparse
import os
import sys
import textwrap
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="")
    parser.add_argument("--role", default="user")
    parser.add_argument("--id", type=int, default=0, help="Force numeric user id (optional)")
    args = parser.parse_args()

    if not HOST or not PASSWORD:
        print("Missing SPAINZA_SSH_HOST / SPAINZA_SSH_PASSWORD in .env.deploy", file=sys.stderr)
        return 1

    py = textwrap.dedent(
        f"""
        import sys
        sys.path.insert(0, "/app/backend")
        import sqlite3
        from werkzeug.security import generate_password_hash
        from models.user import random_user_display_id, get_user_by_email

        email = {args.email!r}.lower()
        password = {args.password!r}
        name = {args.name!r} or email.split("@")[0].title()
        role = {args.role!r}
        forced_id = {args.id}

        conn = sqlite3.connect("/app/database/app.db")
        conn.row_factory = sqlite3.Row

        existing = get_user_by_email(conn, email)
        pwd_hash = generate_password_hash(password)

        if existing:
            uid = int(existing["id"])
            conn.execute(
                "UPDATE users SET password_hash=?, role_key=?, name=?, "
                "profile_setup_completed=1, email_verified_at=COALESCE(email_verified_at, datetime('now')), "
                "email_verification_token_hash=NULL WHERE id=?",
                (pwd_hash, role, name, uid),
            )
            conn.commit()
            print(f"UPDATED user id={{uid}} email={{email}} role={{role}}")
        else:
            display_id = random_user_display_id()
            if forced_id > 0:
                conn.execute(
                    '''
                    INSERT INTO users (
                        id, email, password_hash, role_key, display_id, name,
                        profile_setup_completed, email_verified_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'))
                    ''',
                    (forced_id, email, pwd_hash, role, display_id, name),
                )
                conn.execute(
                    "INSERT INTO sqlite_sequence (name, seq) VALUES ('users', ?) "
                    "ON CONFLICT(name) DO UPDATE SET seq=max(seq, excluded.seq)",
                    (forced_id,),
                )
                uid = forced_id
            else:
                cur = conn.execute(
                    '''
                    INSERT INTO users (
                        email, password_hash, role_key, display_id, name,
                        profile_setup_completed, email_verified_at
                    ) VALUES (?, ?, ?, ?, ?, 1, datetime('now'))
                    ''',
                    (email, pwd_hash, role, display_id, name),
                )
                uid = int(cur.lastrowid)
            conn.commit()
            print(f"CREATED user id={{uid}} email={{email}} role={{role}} display_id={{display_id}}")

        row = conn.execute(
            "SELECT id, email, role_key, display_id, name FROM users WHERE id=?",
            (uid,),
        ).fetchone()
        print("RESULT", dict(row))
        conn.close()
        """
    ).strip()

    remote_script = f"{REPO}/_create_user.py"
    remote_cmd = (
        f"cd {REPO} && docker compose --env-file .env.production "
        f"-f docker-compose.production.yml exec -T spainza-backend "
        f"python - < {remote_script} && rm -f {remote_script}"
    )

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print(f"Connecting to {HOST}...")
    client.connect(HOST, username=USER, password=PASSWORD, timeout=30)
    sftp = client.open_sftp()
    with sftp.file(remote_script, "w") as remote_file:
        remote_file.write(py)
    sftp.close()
    print("Creating user...")
    _, stdout, stderr = client.exec_command(remote_cmd, timeout=120)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    print(out)
    if err:
        print(err, file=sys.stderr)
    client.close()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
