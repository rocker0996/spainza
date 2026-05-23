# -*- coding: utf-8 -*-
from pathlib import Path
b = Path("frontend/lk/dashboard.html").read_bytes()
good = "\u0413\u043b\u0430\u0432\u043d\u0430\u044f".encode("utf-8")
bad = b"\xd0\xa0\xe2\x80\x9c"
print("has_glavnaya", good in b)
print("has_mojibake", bad in b)
# visible text lines only
text = Path("frontend/lk/dashboard.html").read_text(encoding="utf-8")
for i, line in enumerate(text.splitlines(), 1):
    if "data-i18n" in line and any(c in line for c in ["\u0420\u201c", "\u0420\u00bb"]):
        if "Р" in line and "Глав" not in line and "Кли" not in line:
            print("suspect", i, line[:90])
