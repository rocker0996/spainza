# Telegram Bot UX and Login Corrections Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Обновить постоянную клавиатуру, удалить отправку вопросов через бота, связать FAQ с чатом менеджера и восстановить browser polling Telegram-входа.

**Architecture:** Telegram views получают URL чата менеджера от bot service и используют единые callback-идентификаторы для reply/inline меню. Login page заранее открывает отдельное окно по пользовательскому клику, а исходная вкладка продолжает polling.

**Tech Stack:** Python, SQLite, Telegram Bot API, vanilla JavaScript, unittest.

## Global Constraints

- Не добавлять в FAQ перечень ограничений загрузки.
- Не отправлять сообщения менеджеру через Telegram bot.
- Сохранить RU/EN, привязку аккаунта и существующие уведомления.

---

### Task 1: Актуальная нижняя клавиатура

**Files:** `backend/services/telegram_bot.py`, `backend/services/telegram_views.py`, `backend/test_telegram_views.py`.

- [ ] Написать тест, ожидающий шесть reply-кнопок и отсутствие «Задать вопрос».
- [ ] Запустить `python -m unittest backend.test_telegram_views -v` и увидеть ожидаемое падение.
- [ ] Сопоставить reply-кнопки с `tasks`, `documents`, `case`, `faq`, `portal`, `settings`; убрать `nav:ask` из inline-меню.
- [ ] Повторить тесты и закоммитить `fix: align Telegram reply menu with assistant features`.

### Task 2: FAQ открывает кабинет сообщений

**Files:** `backend/services/telegram_bot.py`, `backend/services/telegram_views.py`, `backend/services/telegram_faq.py`, `backend/test_telegram_faq.py`.

- [ ] Написать тесты: «Это помогло» использует `nav:home`; manager CTA — URL, а не callback; upload article не содержит технических лимитов.
- [ ] Увидеть падение тестов.
- [ ] Добавить helper, который получает primary manager и строит `messages.html?openUserId=<display_id>`, с fallback на `messages.html`.
- [ ] Удалить question callbacks, imports и runtime routing; оставить старые таблицы совместимыми, но неиспользуемыми.
- [ ] Повторить тесты и закоммитить `fix: route Telegram FAQ questions to portal chat`.

### Task 3: Browser-preserving Telegram login

**Files:** `frontend/js/login.js`, `frontend/js/login-i18n.js`, `tests/test_telegram_login_browser_flow.py`.

- [ ] Написать статический regression test: запрещён `window.location.href = target`; окно создаётся до первого `await`; polling остаётся после открытия Telegram.
- [ ] Увидеть падение теста.
- [ ] На click синхронно открыть blank window; после создания login-сессии направить окно в Telegram; при popup-block показать обычную ссылку и продолжить polling исходной страницы.
- [ ] Повторить тесты и закоммитить `fix: preserve browser polling during Telegram login`.

### Task 4: Проверка и поставка

**Files:** существующие тесты и документация.

- [ ] Запустить все Telegram unittest, `npm.cmd test`, `python -m compileall -q backend`, UTF-8 и `git diff --check`.
- [ ] Проверить diff на остатки `nav:ask`, runtime imports question flow и старые reply labels.
- [ ] Push `codex/telegram-client-assistant`.
- [ ] Запустить `tools/remote_deploy.py`; проверить production health, dashboard HTTP 200 и Telegram worker logs.
