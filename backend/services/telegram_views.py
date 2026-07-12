"""Telegram-neutral views and navigation for the client assistant."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional


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
