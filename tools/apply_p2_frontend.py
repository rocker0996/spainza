#!/usr/bin/env python3
"""P2: defer on external scripts, dedupe Material Symbols font links (LK pages only)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
LK_DIR = FRONTEND / "lk"

MATERIAL_ONLY = re.compile(
    r'<link\s+href="https://fonts\.googleapis\.com/css2\?family=Material\+Symbols\+Outlined[^"]*"\s+rel="stylesheet"/>\s*',
    re.IGNORECASE,
)

DUP_MATERIAL = re.compile(
    r'(<link\s+href="https://fonts\.googleapis\.com/css2\?family=Material\+Symbols\+Outlined[^"]*"\s+rel="stylesheet"/>)\s*\1\s*',
    re.IGNORECASE | re.DOTALL,
)

SCRIPT_SRC = re.compile(
    r"<script\s+([^>]*?)src=(\"[^\"]+\"|'[^']+')([^>]*)>",
    re.IGNORECASE | re.DOTALL,
)


def _has_attr(attrs: str, name: str) -> bool:
    return re.search(rf"\b{name}\b", attrs, re.IGNORECASE) is not None


def add_defer_to_scripts(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        before, src, after = match.group(1), match.group(2), match.group(3)
        combined = before + after
        if _has_attr(combined, "defer") or _has_attr(combined, "async"):
            return match.group(0)
        if "type=" in combined.lower() and "module" in combined.lower():
            return match.group(0)
        return f"<script {before}src={src} defer{after}>"

    return SCRIPT_SRC.sub(repl, text)


def _has_combined_text_and_symbols_fonts(text: str) -> bool:
    """True when one stylesheet URL loads Manrope/Inter together with Material Symbols."""
    return bool(
        re.search(
            r"fonts\.googleapis\.com/css2\?family="
            r"(?=[^\"']*Material\+Symbols\+Outlined)"
            r"(?=[^\"']*(?:Manrope|Inter))[^\"']+",
            text,
            re.IGNORECASE,
        )
    )


def dedupe_material_symbols(text: str) -> str:
    text = DUP_MATERIAL.sub(r"\1\n", text)
    if not _has_combined_text_and_symbols_fonts(text):
        return text
    # Drop extra Material-only links only when Symbols already load with text fonts.
    return MATERIAL_ONLY.sub("", text)


MATERIAL_LINK = (
    '<link href="https://fonts.googleapis.com/css2?family=Material+Symbols+Outlined'
    ':wght,FILL@100..700,0..1&amp;display=swap" rel="stylesheet"/>\n'
)


def ensure_material_symbols_if_used(text: str) -> str:
    if "material-symbols-outlined" not in text:
        return text
    if "Material+Symbols+Outlined" in text:
        return text
    text_fonts = re.search(
        r'<link href="https://fonts\.googleapis\.com/css2\?family=(?:Inter|Manrope)[^"]+" rel="stylesheet"/>',
        text,
        re.IGNORECASE,
    )
    if text_fonts:
        insert_at = text_fonts.end()
        return text[:insert_at] + "\n" + MATERIAL_LINK + text[insert_at:]
    return MATERIAL_LINK + text


def patch_file(path: Path) -> bool:
    original = path.read_text(encoding="utf-8")
    text = dedupe_material_symbols(original)
    text = ensure_material_symbols_if_used(text)
    text = add_defer_to_scripts(text)
    if text != original:
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main() -> None:
    paths = sorted(LK_DIR.rglob("*.html"))
    changed = 0
    for path in paths:
        if patch_file(path):
            print(f"patched {path.relative_to(ROOT)}")
            changed += 1
    print(f"done: {changed} file(s) updated")


if __name__ == "__main__":
    main()
