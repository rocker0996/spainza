# -*- coding: utf-8 -*-
"""Repair mojibake in frontend/lk/dashboard.html and verify UTF-8."""
from pathlib import Path

DASH = Path("frontend/lk/dashboard.html")

# Canonical Russian fallbacks (must match lk-i18n.js STRINGS.ru)
TEXT = {
    "nav.dashboard": "Главная",
    "nav.clients": "Клиенты",
    "nav.documents": "Документы",
    "nav.configurator": "Шаблоны кейсов",
    "nav.messages": "Сообщения",
    "nav.profile": "Профиль",
    "nav.support": "Поддержка",
    "nav.logout": "Выход",
    "common.interfaceLanguage": "Язык интерфейса",
    "common.langRu": "Русский",
    "dashboard.caseStatus": "Статус кейса",
    "dashboard.documentPack": "Готовый пакет документов",
    "common.viewAll": "Смотреть все",
    "dashboard.managerChat": "Чат с менеджером",
    "common.noMessages": "Нет сообщений",
    "dashboard.quickReplyPlaceholder": "Быстрый ответ...",
    "dashboard.sendMessage": "Отправить сообщение",
    "common.avatar": "Аватар",
    "common.defaultAvatar": "Стандартный аватар пользователя",
}


def repair_mojibake(s: str) -> str:
    out = s
    for _ in range(6):
        try:
            nxt = out.encode("cp1252").decode("utf-8")
        except (UnicodeDecodeError, UnicodeEncodeError):
            break
        if nxt == out:
            break
        out = nxt
    return out


def main() -> None:
    raw = DASH.read_text(encoding="utf-8")
    fixed = repair_mojibake(raw)

    import re

    for key, value in TEXT.items():
        # Replace inner text of data-i18n="key"
        pattern = rf'(data-i18n="{re.escape(key)}">)([^<]*)(</)'
        fixed, n = re.subn(pattern, rf"\1{value}\3", fixed)
        if n == 0 and key in ("common.avatar", "common.defaultAvatar"):
            pattern_alt = rf'(data-i18n-alt="{re.escape(key)}">)([^<]*)'
            # alt is attribute not tag - handle separately below

    # alt / placeholder / title attributes
    fixed = re.sub(
        r'alt="[^"]*"\s+class="w-12 h-12 md:w-10 md:h-10[^"]*"[^>]*data-alt="[^"]*"',
        f'alt="{TEXT["common.avatar"]}" class="w-12 h-12 md:w-10 md:h-10 rounded-full object-cover shadow-[0_10px_20px_rgba(117,118,130,0.1)]" data-alt="{TEXT["common.defaultAvatar"]}"',
        fixed,
        count=1,
    )
    fixed = re.sub(
        r'id="dashboard-last-message-avatar"[^>]*alt="[^"]*"',
        f'id="dashboard-last-message-avatar" src="../img/Avatar.jpg" alt="{TEXT["common.avatar"]}"',
        fixed,
        count=1,
    )
    fixed = re.sub(
        r'data-i18n-placeholder="dashboard\.quickReplyPlaceholder" placeholder="[^"]*"',
        f'data-i18n-placeholder="dashboard.quickReplyPlaceholder" placeholder="{TEXT["dashboard.quickReplyPlaceholder"]}"',
        fixed,
    )
    fixed = re.sub(
        r'data-i18n-title="dashboard\.sendMessage" title="[^"]*"',
        f'data-i18n-title="dashboard.sendMessage" title="{TEXT["dashboard.sendMessage"]}"',
        fixed,
    )

    # CSS comments — replace broken Russian comments with English
    fixed = re.sub(
        r"/\* Р[^\n]*\*/",
        lambda m: "/* layout */" if "dashboard-id" in m.group(0) or "Ячейка" in repair_mojibake(m.group(0)) else m.group(0),
        fixed,
    )

    DASH.write_text(fixed, encoding="utf-8", newline="\n")

    b = DASH.read_bytes()
    assert "Главная".encode("utf-8") in b, "nav.dashboard not valid UTF-8"
    assert b"\xd0\xa0\xe2\x80\x9c" not in b, "mojibake bytes still present"
    print("OK:", DASH, "— Главная found, mojibake gone")


if __name__ == "__main__":
    main()
