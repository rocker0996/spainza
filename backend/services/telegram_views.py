"""Telegram-neutral views and navigation for the client assistant."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

from services.telegram_client_summary import ClientSummary
from services.telegram_faq import FAQ_CATEGORIES, get_faq, search_faq
from services.telegram_questions import QUESTION_CATEGORIES
from models.telegram_preferences import TelegramPreferences
from services.notification_service import lk_url


@dataclass(frozen=True)
class BotButton:
    text: str
    callback_data: Optional[str] = None
    url: Optional[str] = None


@dataclass(frozen=True)
class BotView:
    text: str
    rows: list[list[BotButton]]


def render_markup(view: BotView) -> dict[str, object]:
    return {
        "inline_keyboard": [
            [
                {key: value for key, value in asdict(button).items() if value is not None}
                for button in row
            ]
            for row in view.rows
        ]
    }


def navigation_rows(back_callback: str, locale: str) -> list[list[BotButton]]:
    ru = locale == "ru"
    return [
        [
            BotButton("← Назад" if ru else "← Back", callback_data=back_callback),
            BotButton("🏠 Главное меню" if ru else "🏠 Main menu", callback_data="nav:home"),
        ]
    ]


def build_main_menu(locale: str, *, task_count: int = 0, active_stage: str = "—") -> BotView:
    ru = locale == "ru"
    if ru:
        text = (
            "🏠 Spainza · Личный помощник\n\n"
            f"⚠️ Текущие задачи: {task_count}\n"
            f"🔵 Этап: {active_stage or '—'}\n\n"
            "Выберите раздел:"
        )
        labels = [
            "✅ Что нужно сделать",
            "📄 Документы",
            "📍 Мой кейс",
            "💬 Задать вопрос",
            "📚 Частые вопросы",
            "⚙️ Настройки",
        ]
    else:
        text = (
            "🏠 Spainza · Client assistant\n\n"
            f"⚠️ Current tasks: {task_count}\n"
            f"🔵 Stage: {active_stage or '—'}\n\n"
            "Choose a section:"
        )
        labels = [
            "✅ What to do",
            "📄 Documents",
            "📍 My case",
            "💬 Ask a question",
            "📚 FAQ",
            "⚙️ Settings",
        ]
    callbacks = ["nav:tasks", "nav:docs", "nav:case", "nav:ask", "nav:faq", "nav:settings"]
    return BotView(
        text,
        [[BotButton(label, callback_data=callback)] for label, callback in zip(labels, callbacks)],
    )


def build_tasks_view(locale: str, summary: ClientSummary) -> BotView:
    ru = locale == "ru"
    if not summary.tasks:
        text = (
            "✅ Что нужно сделать\n\nСейчас от вас не требуется никаких действий."
            if ru
            else "✅ What to do\n\nNo action is required from you right now."
        )
        return BotView(text, navigation_rows("nav:home", locale))

    lines = ["✅ Что нужно сделать" if ru else "✅ What to do"]
    rows: list[list[BotButton]] = []
    for index, task in enumerate(summary.tasks, start=1):
        marker = "❌" if task.kind == "reupload" else "⚠️"
        lines.extend(["", f"{index}. {marker} {task.title}"])
        if task.due_at:
            lines.append(("Срок: " if ru else "Due: ") + task.due_at)
        if task.detail:
            detail = "Срочно" if ru and task.detail == "urgent" else "Urgent" if task.detail == "urgent" else task.detail
            lines.append(detail)
        rows.append([BotButton("Открыть задачу" if ru else "Open task", url=task.url)])
    rows.extend(navigation_rows("nav:home", locale))
    return BotView("\n".join(lines), rows)


def build_documents_view(locale: str, summary: ClientSummary, category: Optional[str] = None) -> BotView:
    ru = locale == "ru"
    docs = summary.documents
    if category:
        matching = {
            "review": {"pending"},
            "approved": {"approved"},
            "fix": {"rejected"},
        }.get(category, set())
        lines = ["📄 Документы" if ru else "📄 Documents"]
        for item in docs.items:
            if item.status not in matching:
                continue
            lines.extend(["", f"• {item.title}"])
            if item.detail:
                lines.append(("Комментарий: " if ru else "Comment: ") + item.detail)
        if len(lines) == 1:
            lines.extend(["", "В этой категории документов нет." if ru else "There are no documents in this category."])
        rows = [[BotButton("📎 Открыть документы" if ru else "📎 Open documents", url=lk_url("/frontend/lk/documents.html"))]]
        rows.extend(navigation_rows("nav:docs", locale))
        return BotView("\n".join(lines), rows)

    text = (
        "📄 Документы\n\n"
        f"⚠️ Ожидают загрузки: {docs.pending_upload}\n"
        f"🔵 На проверке: {docs.in_review}\n"
        f"✅ Одобрены: {docs.approved}\n"
        f"❌ Нужно исправить: {docs.needs_fix}"
        if ru
        else "📄 Documents\n\n"
        f"⚠️ Pending upload: {docs.pending_upload}\n"
        f"🔵 In review: {docs.in_review}\n"
        f"✅ Approved: {docs.approved}\n"
        f"❌ Needs fixing: {docs.needs_fix}"
    )
    rows = [
        [BotButton("⚠️ Ожидают загрузки" if ru else "⚠️ Pending upload", callback_data="docs:pending")],
        [BotButton("🔵 На проверке" if ru else "🔵 In review", callback_data="docs:review")],
        [BotButton("✅ Одобрены" if ru else "✅ Approved", callback_data="docs:approved")],
        [BotButton("❌ Нужно исправить" if ru else "❌ Needs fixing", callback_data="docs:fix")],
    ]
    rows.extend(navigation_rows("nav:home", locale))
    return BotView(text, rows)


def build_case_view(locale: str, summary: ClientSummary) -> BotView:
    ru = locale == "ru"
    lines = ["📍 Мой кейс" if ru else "📍 My case"]
    markers = {"completed": "✅", "active": "🔵", "pending": "⚪"}
    if summary.case.steps:
        lines.append("")
        for step in summary.case.steps:
            lines.append(f"{markers.get(step.status, '⚪')} {step.title}")
        if summary.case.active_description:
            lines.extend(["", summary.case.active_description])
        if summary.case.updated_at:
            lines.extend(["", ("Обновлено: " if ru else "Updated: ") + summary.case.updated_at])
    else:
        lines.extend(["", "Данные о текущем этапе пока не добавлены." if ru else "Current stage data has not been added yet."])
    rows = navigation_rows("nav:home", locale)
    return BotView("\n".join(lines), rows)


def build_client_section_view(
    callback_data: str,
    locale: str,
    summary: ClientSummary,
) -> Optional[BotView]:
    if callback_data == "nav:tasks":
        return build_tasks_view(locale, summary)
    if callback_data == "nav:docs":
        return build_documents_view(locale, summary)
    if callback_data == "nav:case":
        return build_case_view(locale, summary)
    if callback_data.startswith("docs:"):
        return build_documents_view(locale, summary, callback_data.split(":", 1)[1])
    return None


def build_faq_view(locale: str, target: Optional[str] = None) -> BotView:
    ru = locale == "ru"
    if not target:
        rows = [
            [BotButton(labels[0] if ru else labels[1], callback_data=f"faq:cat:{category}")]
            for category, labels in FAQ_CATEGORIES.items()
        ]
        rows.extend(navigation_rows("nav:home", locale))
        return BotView(
            "📚 Частые вопросы\n\nВыберите тему:" if ru else "📚 Frequently asked questions\n\nChoose a topic:",
            rows,
        )

    if target.startswith("cat:"):
        category = target.split(":", 1)[1]
        articles = search_faq(locale, category)
        rows = [[BotButton(article.title(locale), callback_data=f"faq:{article.article_id}")] for article in articles]
        rows.extend(navigation_rows("nav:faq", locale))
        return BotView(
            "📚 " + ("Вопросы по теме" if ru else "Questions in this topic"),
            rows,
        )

    article = get_faq(locale, target)
    if not article:
        return BotView(
            "Ответ не найден." if ru else "Answer not found.",
            navigation_rows("nav:faq", locale),
        )
    rows = [
        [BotButton("👍 Это помогло" if ru else "👍 This helped", callback_data=f"faq:helped:{article.article_id}")],
        [
            BotButton(
                "💬 Задать вопрос менеджеру" if ru else "💬 Ask a manager",
                callback_data=f"ask:start:{article.category}",
            )
        ],
    ]
    rows.extend(navigation_rows(f"faq:cat:{article.category}", locale))
    return BotView(f"📚 {article.title(locale)}\n\n{article.body(locale)}", rows)


def build_question_categories_view(locale: str) -> BotView:
    ru = locale == "ru"
    rows = [
        [BotButton(labels[0] if ru else labels[1], callback_data=f"ask:start:{category}")]
        for category, labels in QUESTION_CATEGORIES.items()
    ]
    rows.extend(navigation_rows("nav:home", locale))
    return BotView(
        "💬 Задать вопрос\n\nВыберите тему:" if ru else "💬 Ask a question\n\nChoose a topic:",
        rows,
    )


def build_question_prompt_view(locale: str, category: str) -> BotView:
    ru = locale == "ru"
    labels = QUESTION_CATEGORIES.get(category, QUESTION_CATEGORIES["other"])
    topic = labels[0] if ru else labels[1]
    text = (
        f"💬 {topic}\n\nНапишите вопрос одним сообщением. Я добавлю к нему данные вашего кейса.\n\n/cancel — отменить"
        if ru
        else f"💬 {topic}\n\nWrite your question in one message. I will attach your case context.\n\n/cancel — cancel"
    )
    return BotView(text, navigation_rows("nav:ask", locale))


def build_settings_view(locale: str, preferences: TelegramPreferences) -> BotView:
    ru = locale == "ru"
    labels = {
        "messages": ("Сообщения менеджера", "Manager messages"),
        "documents": ("Документы", "Documents"),
        "case_updates": ("Изменения кейса", "Case updates"),
        "reminders": ("Напоминания", "Reminders"),
        "digest_enabled": ("Ежедневный дайджест", "Daily digest"),
    }
    rows: list[list[BotButton]] = []
    for field, pair in labels.items():
        enabled = bool(getattr(preferences, field))
        rows.append(
            [
                BotButton(
                    f"{'✅' if enabled else '❌'} {pair[0] if ru else pair[1]}",
                    callback_data=f"set:{field}:{0 if enabled else 1}",
                )
            ]
        )
    rows.append(
        [
            BotButton(
                "🌐 English" if ru else "🌐 Русский",
                callback_data="set:lang:en" if ru else "set:lang:ru",
            )
        ]
    )
    rows.extend(navigation_rows("nav:home", locale))
    return BotView(
        "⚙️ Настройки\n\nНажмите, чтобы включить или отключить уведомления."
        if ru
        else "⚙️ Settings\n\nTap to enable or disable notifications.",
        rows,
    )
