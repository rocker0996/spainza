"""Load local deploy credentials from gitignored .env.deploy (never commit)."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_ENV_PATH = ROOT / ".env.deploy"


def load_deploy_env() -> None:
    """Populate os.environ from .env.deploy when keys are not already set."""
    if not DEPLOY_ENV_PATH.is_file():
        return
    for raw_line in DEPLOY_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value
