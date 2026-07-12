# Telegram Client Assistant Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Превратить Telegram-бота Spainza в клиентский ассистент с задачами, документами, кейсом, FAQ, структурированными вопросами, настройками и напоминаниями.

**Architecture:** Тонкий Telegram-router передаёт callback-события независимым сценариям, которые получают данные через read-модель клиента и возвращают Telegram-neutral `BotView`. Состояние диалогов, настройки и расписание хранятся в SQLite; все фоновые доставки идут через расширенный notification outbox.

**Tech Stack:** Python 3, Flask, SQLite, Telegram Bot HTTP API, unittest/pytest-compatible tests.

## Global Constraints

- Персональные данные доступны только для активной привязки `chat_id` к пользователю.
- Загрузка файлов и критичные действия остаются в защищённом личном кабинете.
- Все пользовательские тексты доступны на русском и английском языках.
- Существующие `/start`, `/status`, `/help`, `/unlink`, привязка и Telegram login сохраняют обратную совместимость.
- Callback identifiers не содержат персональных данных и укладываются в лимит Telegram `callback_data`.
- Пользовательский ввод отправляется без HTML/Markdown parse mode.

---

### Task 1: Telegram-neutral представление и навигация

**Files:**
- Create: `backend/services/telegram_views.py`
- Create: `backend/test_telegram_views.py`
- Modify: `backend/services/telegram_api.py`
- Modify: `backend/services/telegram_bot.py`

**Interfaces:**
- Produces: `BotButton(text: str, callback_data: str | None = None, url: str | None = None)`, `BotView(text: str, rows: list[list[BotButton]])`, `render_markup(view: BotView) -> dict`, `edit_message_text(...)`.

- [ ] **Step 1: Write failing view and navigation tests**

```python
def test_main_menu_has_six_actions_and_no_personal_callback_data():
    view = build_main_menu("ru", task_count=3, active_stage="Проверка")
    callbacks = [b.callback_data for row in view.rows for b in row]
    assert callbacks == ["nav:tasks", "nav:docs", "nav:case", "nav:ask", "nav:faq", "nav:settings"]
    assert "3" in view.text and "Проверка" in view.text

def test_nested_view_always_has_back_and_home():
    rows = navigation_rows("nav:tasks")
    assert [b.callback_data for b in rows[-1]] == ["nav:tasks", "nav:home"]
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest backend/test_telegram_views.py -v`
Expected: FAIL because `services.telegram_views` does not exist.

- [ ] **Step 3: Implement immutable view objects and RU/EN menu builders**

```python
@dataclass(frozen=True)
class BotButton:
    text: str
    callback_data: str | None = None
    url: str | None = None

@dataclass(frozen=True)
class BotView:
    text: str
    rows: list[list[BotButton]]

def render_markup(view: BotView) -> dict[str, object]:
    return {"inline_keyboard": [[{k: v for k, v in asdict(button).items() if v} for button in row] for row in view.rows]}
```

- [ ] **Step 4: Add Telegram `editMessageText` support and navigation fallback**

```python
def edit_message_text(token: str, chat_id: int, message_id: int, text: str, *, reply_markup=None):
    return _request(token, "editMessageText", {"chat_id": chat_id, "message_id": message_id, "text": text, "reply_markup": reply_markup})
```

Router edits the callback's source message; if Telegram rejects editing, it sends a new message. `/start` and unknown text open the same main menu.

- [ ] **Step 5: Run focused and smoke tests**

Run: `python -m pytest backend/test_telegram_views.py backend/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/services/telegram_views.py backend/services/telegram_api.py backend/services/telegram_bot.py backend/test_telegram_views.py
git commit -m "feat: add Telegram assistant navigation"
```

### Task 2: Read-модель задач, документов и кейса

**Files:**
- Create: `backend/services/telegram_client_summary.py`
- Create: `backend/test_telegram_client_summary.py`
- Modify: `backend/services/telegram_views.py`
- Modify: `backend/services/telegram_bot.py`

**Interfaces:**
- Produces: `ClientTask`, `DocumentSummary`, `CaseSummary`; `load_client_summary(connection, user_id) -> ClientSummary`.
- Consumes: existing `get_case_data_by_user_id`, document rows and application progress data.

- [ ] **Step 1: Write failing normalization tests**

```python
def test_summary_collects_pending_rejected_and_active_stage(db, client):
    seed_case(db, client, pending_request="Справка", active_stage="Проверка")
    seed_document(db, client, title="Договор", status="rejected", rejection_comment="Нет страницы")
    summary = load_client_summary(db, client)
    assert [x.kind for x in summary.tasks] == ["reupload", "upload"]
    assert summary.documents.needs_fix == 1
    assert summary.case.active_title == "Проверка"

def test_empty_summary_does_not_invent_dates_or_steps(db, client):
    summary = load_client_summary(db, client)
    assert summary.tasks == []
    assert summary.case.active_title is None
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest backend/test_telegram_client_summary.py -v`
Expected: FAIL because summary service does not exist.

- [ ] **Step 3: Implement typed normalization**

```python
@dataclass(frozen=True)
class ClientTask:
    kind: Literal["upload", "reupload", "client_action"]
    title: str
    due_at: str | None
    detail: str | None
    url: str

@dataclass(frozen=True)
class DocumentSummary:
    pending_upload: int = 0
    in_review: int = 0
    approved: int = 0
    needs_fix: int = 0
```

Sort tasks by due date, then severity, then title. Never expose documents belonging to another user.

- [ ] **Step 4: Build tasks, document-category and timeline views**

```python
def build_tasks_view(locale: str, summary: ClientSummary) -> BotView: ...
def build_documents_view(locale: str, summary: ClientSummary, category: str | None = None) -> BotView: ...
def build_case_view(locale: str, summary: ClientSummary) -> BotView: ...
```

Callbacks: `nav:tasks`, `nav:docs`, `docs:pending`, `docs:review`, `docs:approved`, `docs:fix`, `nav:case`.

- [ ] **Step 5: Route sections with fresh authorization checks**

Every callback resolves `user_id` from active `chat_id` before loading the summary. Missing links render the guest menu.

- [ ] **Step 6: Run tests and commit**

Run: `python -m pytest backend/test_telegram_client_summary.py backend/test_telegram_views.py backend/test_smoke.py -v`
Expected: PASS.

```powershell
git add backend/services/telegram_client_summary.py backend/services/telegram_views.py backend/services/telegram_bot.py backend/test_telegram_client_summary.py
git commit -m "feat: show client tasks documents and case in Telegram"
```

### Task 3: RU/EN FAQ

**Files:**
- Create: `backend/services/telegram_faq.py`
- Create: `backend/test_telegram_faq.py`
- Modify: `backend/services/telegram_views.py`
- Modify: `backend/services/telegram_bot.py`

**Interfaces:**
- Produces: `FAQ_CATEGORIES`, `get_faq(locale, article_id) -> FaqArticle | None`, `search_faq(locale, category) -> list[FaqArticle]`.

- [ ] **Step 1: Write failing content and routing tests**

```python
def test_every_faq_article_has_ru_and_en():
    for article in FAQ_ARTICLES.values():
        assert article.title_ru and article.body_ru and article.title_en and article.body_en

def test_faq_callback_ids_fit_telegram_limit():
    assert all(len(f"faq:{key}".encode()) <= 64 for key in FAQ_ARTICLES)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest backend/test_telegram_faq.py -v`
Expected: FAIL because FAQ module does not exist.

- [ ] **Step 3: Add curated categories and articles**

```python
@dataclass(frozen=True)
class FaqArticle:
    category: str
    title_ru: str
    body_ru: str
    title_en: str
    body_en: str
```

Include documents, translations/apostille, file formats, review timing, statuses, rejected documents and portal access. Legal/process answers must avoid guarantees and direct case-specific questions to a manager.

- [ ] **Step 4: Add FAQ category/article views and feedback buttons**

Article actions: `faq:helped:<id>` and `ask:start:<category>`. Guests may use the full FAQ.

- [ ] **Step 5: Run tests and commit**

Run: `python -m pytest backend/test_telegram_faq.py backend/test_telegram_views.py -v`
Expected: PASS.

```powershell
git add backend/services/telegram_faq.py backend/services/telegram_views.py backend/services/telegram_bot.py backend/test_telegram_faq.py
git commit -m "feat: add Telegram FAQ"
```

### Task 4: Устойчивый сценарий вопроса менеджеру

**Files:**
- Create: `backend/models/telegram_conversation.py`
- Create: `backend/services/telegram_questions.py`
- Create: `backend/test_telegram_questions.py`
- Modify: `backend/services/telegram_bot.py`
- Modify: `backend/models/notifications.py`

**Interfaces:**
- Produces: `start_question(connection, user_id, chat_id, category)`, `consume_question_text(..., update_id, text) -> QuestionResult`, `cancel_question(...)`.
- Consumes: existing message/conversation creation service and manager assignment.

- [ ] **Step 1: Write failing state/idempotency tests**

```python
def test_question_survives_service_restart_and_sends_once(db, linked_client):
    start_question(db, linked_client.user_id, linked_client.chat_id, "documents")
    first = consume_question_text(db, linked_client.chat_id, update_id=77, text="Какой перевод нужен?")
    second = consume_question_text(db, linked_client.chat_id, update_id=77, text="Какой перевод нужен?")
    assert first.created is True
    assert second.created is False
    assert count_client_messages(db, linked_client.user_id) == 1
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest backend/test_telegram_questions.py -v`
Expected: FAIL because conversation state module does not exist.

- [ ] **Step 3: Add tables via idempotent bootstrap**

```sql
CREATE TABLE IF NOT EXISTS telegram_dialog_states (
  chat_id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, flow TEXT NOT NULL,
  category TEXT, context_json TEXT NOT NULL DEFAULT '{}', expires_at TEXT NOT NULL,
  updated_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS telegram_processed_updates (
  update_id INTEGER PRIMARY KEY, processed_at TEXT NOT NULL
);
```

- [ ] **Step 4: Implement category selection, FAQ suggestions, free text and cancel**

The created portal message starts with a localized structured header containing category, active stage and selected document, followed by the exact user text. `/cancel` and `nav:home` clear the state; state expires after 30 minutes.

- [ ] **Step 5: Route non-command text only when a question state is active**

Outside the flow, text opens the main menu and explains how to choose «Задать вопрос». Guests are asked to link their account.

- [ ] **Step 6: Run tests and commit**

Run: `python -m pytest backend/test_telegram_questions.py backend/test_smoke.py -v`
Expected: PASS.

```powershell
git add backend/models/telegram_conversation.py backend/models/notifications.py backend/services/telegram_questions.py backend/services/telegram_bot.py backend/test_telegram_questions.py
git commit -m "feat: let clients ask structured questions in Telegram"
```

### Task 5: Контекстные уведомления и категории доставки

**Files:**
- Create: `backend/models/telegram_preferences.py`
- Create: `backend/test_telegram_notifications.py`
- Modify: `backend/services/notification_service.py`
- Modify: `backend/services/telegram_worker.py`
- Modify: `backend/services/telegram_views.py`
- Modify: `backend/services/telegram_bot.py`

**Interfaces:**
- Produces: `TelegramPreferences`, `get_preferences`, `update_preferences`, `category_for_event(event_type)`, `delivery_decision(...)`.

- [ ] **Step 1: Write failing preference/action tests**

```python
def test_document_rejection_has_reason_and_reupload_actions():
    text, markup = build_telegram_message(EVENT_DOCUMENT_REJECTED, rejected_payload())
    labels = [b["text"] for row in markup["inline_keyboard"] for b in row]
    assert labels == ["❌ Посмотреть причину", "🔄 Загрузить заново"]

def test_disabled_category_keeps_event_but_skips_telegram_delivery(db, client):
    update_preferences(db, client, documents=False)
    event_id = notify(db, client, EVENT_DOCUMENT_APPROVED, approved_payload())
    assert event_id is None
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest backend/test_telegram_notifications.py -v`
Expected: FAIL because preferences do not exist.

- [ ] **Step 3: Add preferences table and defaults**

```sql
CREATE TABLE IF NOT EXISTS telegram_preferences (
  user_id INTEGER PRIMARY KEY, locale TEXT, messages INTEGER NOT NULL DEFAULT 1,
  documents INTEGER NOT NULL DEFAULT 1, case_updates INTEGER NOT NULL DEFAULT 1,
  reminders INTEGER NOT NULL DEFAULT 1, quiet_start TEXT, quiet_end TEXT,
  digest_enabled INTEGER NOT NULL DEFAULT 0, digest_time TEXT NOT NULL DEFAULT '09:00',
  FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

- [ ] **Step 4: Add settings view and toggle callbacks**

Callbacks use `set:<field>:0|1` and `set:lang:ru|en`; only allowlisted fields are accepted. Locale changes update the bot preference and the existing user locale consistently.

- [ ] **Step 5: Upgrade notification action buttons**

Message → answer/open chat; request → list/upload; rejection → reason/re-upload; stage → explanation/next action. Callback actions render data from a fresh authorized summary.

- [ ] **Step 6: Run tests and commit**

Run: `python -m pytest backend/test_telegram_notifications.py backend/test_telegram_views.py backend/test_smoke.py -v`
Expected: PASS.

```powershell
git add backend/models/telegram_preferences.py backend/services/notification_service.py backend/services/telegram_worker.py backend/services/telegram_views.py backend/services/telegram_bot.py backend/test_telegram_notifications.py
git commit -m "feat: add actionable Telegram notifications and preferences"
```

### Task 6: Напоминания, тихие часы, группировка и дайджест

**Files:**
- Create: `backend/services/telegram_scheduler.py`
- Create: `backend/test_telegram_scheduler.py`
- Modify: `backend/models/notifications.py`
- Modify: `backend/services/telegram_worker.py`
- Modify: `backend/services/notification_service.py`

**Interfaces:**
- Produces: `schedule_due_reminders(connection, now) -> int`, `release_deferred_notifications(connection, now) -> int`, `build_digest(...)`.

- [ ] **Step 1: Write failing scheduling tests with fixed UTC time**

```python
def test_completed_task_cancels_future_reminders(db, client, clock):
    seed_due_task(db, client, due="2026-07-15")
    assert schedule_due_reminders(db, clock("2026-07-12T08:00:00Z")) == 1
    complete_task(db, client)
    release_deferred_notifications(db, clock("2026-07-12T09:00:00Z"))
    assert pending_reminders(db, client) == []

def test_quiet_hours_defer_normal_but_not_urgent(db, client):
    set_quiet_hours(db, client, "22:00", "08:00")
    assert delivery_decision(normal_event(), local_time="23:00") == "defer"
    assert delivery_decision(urgent_event(), local_time="23:00") == "send"
```

- [ ] **Step 2: Run tests and verify failure**

Run: `python -m pytest backend/test_telegram_scheduler.py -v`
Expected: FAIL because scheduler does not exist.

- [ ] **Step 3: Extend outbox for dedupe and deferred delivery**

```sql
ALTER TABLE notification_outbox ADD COLUMN dedupe_key TEXT;
ALTER TABLE notification_outbox ADD COLUMN deliver_after TEXT;
ALTER TABLE notification_outbox ADD COLUMN urgency TEXT NOT NULL DEFAULT 'normal';
CREATE UNIQUE INDEX IF NOT EXISTS idx_notification_outbox_dedupe ON notification_outbox(dedupe_key) WHERE dedupe_key IS NOT NULL;
```

Migration checks columns through `PRAGMA table_info` before each `ALTER TABLE`.

- [ ] **Step 4: Implement deterministic reminder keys and completion recheck**

Keys follow `reminder:<user_id>:<task_kind>:<stable_task_id>:<offset>`. Before delivery, reload the client summary and cancel the row if the task no longer exists.

- [ ] **Step 5: Implement quiet hours, coalescing and daily digest**

Normal events inside quiet hours receive `deliver_after` at quiet-end. Digest users accumulate normal events until their configured local time. Events with the same user/category inside a five-minute window render as one localized summary; message previews from different conversations remain separate entries.

- [ ] **Step 6: Invoke scheduler in worker loop and test retries**

The loop schedules, releases, then processes outbox. A scheduler exception is logged and does not stop polling commands.

- [ ] **Step 7: Run tests and commit**

Run: `python -m pytest backend/test_telegram_scheduler.py backend/test_telegram_notifications.py backend/test_smoke.py -v`
Expected: PASS.

```powershell
git add backend/services/telegram_scheduler.py backend/services/telegram_worker.py backend/services/notification_service.py backend/models/notifications.py backend/test_telegram_scheduler.py
git commit -m "feat: add Telegram reminders quiet hours and digest"
```

### Task 7: Полная регрессия и эксплуатационные проверки

**Files:**
- Create: `backend/test_telegram_bot_integration.py`
- Modify: `.env.example`
- Modify: `README.md`

**Interfaces:**
- Consumes all preceding public service functions; produces no new runtime interface.

- [ ] **Step 1: Add end-to-end mocked Telegram tests**

```python
def test_linked_client_journey(db, telegram_api, linked_client):
    dispatch("/start")
    dispatch_callback("nav:tasks")
    dispatch_callback("nav:docs")
    dispatch_callback("nav:case")
    dispatch_callback("nav:faq")
    dispatch_callback("ask:start:documents")
    dispatch_text("Нужен ли апостиль?", update_id=501)
    assert telegram_api.no_real_requests
    assert count_client_messages(db, linked_client.user_id) == 1

def test_guest_cannot_open_personal_sections(db, telegram_api):
    dispatch_callback("nav:docs", chat_id=999)
    assert telegram_api.last_text_contains("подключ")
```

- [ ] **Step 2: Run the complete backend suite**

Run: `python -m pytest backend -v`
Expected: PASS with no network access.

- [ ] **Step 3: Run project smoke checks**

Run: `npm.cmd test`
Expected: exit code 0.

- [ ] **Step 4: Document worker and settings behavior**

README must describe starting `run_telegram_worker.py`, required `TELEGRAM_BOT_TOKEN`, defaults for reminders/digest and the fact that document upload remains in the portal.

- [ ] **Step 5: Run UTF-8 and diff checks**

Run: `python tools/verify_dashboard_utf8.py; git diff --check`
Expected: both exit code 0.

- [ ] **Step 6: Commit**

```powershell
git add backend/test_telegram_bot_integration.py .env.example README.md
git commit -m "test: cover Telegram client assistant journeys"
```

### Task 8: Final verification

**Files:** no new files.

- [ ] **Step 1: Verify repository state and all tests**

Run: `python -m pytest backend -v; npm.cmd test; git diff --check; git status --short`
Expected: tests pass; diff check is clean; only pre-existing unrelated working-tree changes remain.

- [ ] **Step 2: Manually smoke-test against a configured test bot**

Run: `python run_telegram_worker.py` with a non-production bot token, then exercise `/start`, every menu section, RU/EN switch, question cancellation, notification actions and unlink/relink.
Expected: menus edit in place, notifications remain separate, no personal data is shown after unlinking.

- [ ] **Step 3: Record rollout safeguards**

Deploy schema/bootstrap changes before starting the new worker. Monitor `[telegram-worker]` errors, failed outbox attempts and duplicate-key conflicts. Roll back application code without dropping new nullable/defaulted columns; old worker remains compatible.
