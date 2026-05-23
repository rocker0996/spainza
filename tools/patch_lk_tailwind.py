#!/usr/bin/env python3
"""Replace Tailwind CDN blocks in LK HTML with built portal.css."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LK_DIR = ROOT / "frontend" / "lk"
EXTRA_HTML = [ROOT / "frontend" / "login.html"]
PORTAL_LINK = '<link rel="stylesheet" href="/frontend/css/portal.css?v=1"/>'

CDN_SCRIPT = re.compile(
    r'<script src="https://cdn\.tailwindcss\.com[^"]*"></script>\s*',
    re.DOTALL,
)
TAILWIND_CONFIG = re.compile(
    r'<script id="tailwind-config">.*?</script>\s*',
    re.DOTALL,
)

I18N_BOOT = re.compile(
    r'<style id="lk-i18n-boot">.*?</style>\s*',
    re.DOTALL,
)

DUP_MATERIAL = re.compile(
    r'(<link href="https://fonts\.googleapis\.com/css2\?family=Material\+Symbols\+Outlined[^"]+" rel="stylesheet"/>)\s*\1\s*',
    re.DOTALL,
)


def patch_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    text = I18N_BOOT.sub("", text)
    text = text.replace(' class="light lk-i18n-pending"', ' class="light"')
    text = text.replace('lk-i18n-pending', '', 1) if 'lk-i18n-pending' in text else text

    had_cdn = bool(CDN_SCRIPT.search(text) or TAILWIND_CONFIG.search(text))
    text = CDN_SCRIPT.sub("", text)
    text = TAILWIND_CONFIG.sub("", text)
    if had_cdn and "portal.css" not in text:
        text = text.replace("</title>", "</title>\n" + PORTAL_LINK, 1)
    elif not had_cdn and "portal.css" not in text:
        print(f"  skip (no CDN block): {path.name}")

    text = DUP_MATERIAL.sub(r"\1\n", text)

    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    paths = sorted(LK_DIR.glob("*.html")) + [p for p in EXTRA_HTML if p.is_file()]
    changed = 0
    for path in paths:
        if patch_file(path):
            print(f"patched {path.relative_to(ROOT)}")
            changed += 1
    print(f"done: {changed} file(s) updated")


if __name__ == "__main__":
    main()
