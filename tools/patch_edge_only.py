"""Apply edge nginx upload limit fix on VPS (no full rebuild)."""
from __future__ import annotations

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


def run(client: paramiko.SSHClient, cmd: str) -> int:
    print(f"\n$ {cmd}")
    _, stdout, stderr = client.exec_command(cmd, timeout=120, get_pty=True)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    if out:
        print(out.rstrip())
    if err and code != 0:
        print(err.rstrip(), file=sys.stderr)
    return code


def main() -> int:
    if not PASSWORD:
        print("Set SPAINZA_SSH_PASSWORD", file=sys.stderr)
        return 1

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=HOST,
        username=USER,
        password=PASSWORD,
        timeout=30,
        allow_agent=False,
        look_for_keys=False,
    )

    sftp = client.open_sftp()
    for rel in ("tools/update_edge_nginx.sh", "docker/edge/spainza-site.conf"):
        local = ROOT / rel
        remote = f"{REPO}/{rel.replace(chr(92), '/')}"
        print(f"Upload {local} -> {remote}")
        sftp.put(str(local), remote)
    sftp.close()

    steps = [
        f"sed -i 's/\\r$//' {REPO}/tools/update_edge_nginx.sh {REPO}/docker/edge/spainza-site.conf",
        f"bash {REPO}/tools/update_edge_nginx.sh",
        (
            "python3 - <<'PY'\n"
            "import subprocess, tempfile, os\n"
            "size = 2 * 1024 * 1024\n"
            "fd, path = tempfile.mkstemp(suffix='.bin')\n"
            "os.write(fd, b'0' * size)\n"
            "os.close(fd)\n"
            "code = subprocess.check_output([\n"
            "    'curl', '-sS', '-o', '/dev/null', '-w', '%{http_code}',\n"
            "    '-X', 'POST', '-F', f'file=@{path};filename=test.pdf',\n"
            "    '-H', 'Host: spainza.com', 'http://127.0.0.1/api/documents/upload',\n"
            "], text=True).strip()\n"
            "os.unlink(path)\n"
            "print(f'2MB upload probe: HTTP {code}')\n"
            "raise SystemExit(1 if code == '413' else 0)\n"
            "PY"
        ),
    ]

    for cmd in steps:
        code = run(client, cmd)
        if code != 0:
            client.close()
            return code

    client.close()
    print("\nEdge nginx patch applied.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
