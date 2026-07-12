from __future__ import annotations

from pathlib import Path
import sys
import unittest
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TelegramViewsTest(unittest.TestCase):
    def test_main_menu_has_five_stable_actions_without_question_flow(self) -> None:
        from services.telegram_views import build_main_menu

        view = build_main_menu("ru", task_count=3, active_stage="Проверка")
        callbacks = [button.callback_data for row in view.rows for button in row]

        self.assertEqual(
            callbacks,
            [
                "nav:tasks",
                "nav:docs",
                "nav:case",
                "nav:faq",
                "nav:settings",
            ],
        )
        self.assertIn("3", view.text)
        self.assertIn("Проверка", view.text)

    def test_reply_menu_matches_current_assistant_features(self) -> None:
        from services.telegram_bot import _main_menu_markup

        labels = [button["text"] for row in _main_menu_markup(True)["keyboard"] for button in row]

        self.assertEqual(
            labels,
            [
                "✅ Что нужно сделать",
                "📄 Документы",
                "📍 Мой кейс",
                "📚 Частые вопросы",
                "🏠 Кабинет",
                "⚙️ Настройки",
            ],
        )
        self.assertNotIn("Задать вопрос", " ".join(labels))

    def test_navigation_rows_always_offer_back_and_home(self) -> None:
        from services.telegram_views import navigation_rows

        rows = navigation_rows("nav:tasks", "ru")

        self.assertEqual(
            [button.callback_data for button in rows[-1]],
            ["nav:tasks", "nav:home"],
        )

    def test_render_markup_omits_empty_button_fields(self) -> None:
        from services.telegram_views import BotButton, BotView, render_markup

        markup = render_markup(
            BotView("Menu", [[BotButton("Open", url="https://spainza.com")]])
        )

        self.assertEqual(
            markup,
            {"inline_keyboard": [[{"text": "Open", "url": "https://spainza.com"}]]},
        )

    def test_deliver_view_falls_back_to_new_message_when_edit_fails(self) -> None:
        from services.telegram_api import TelegramApiError
        from services.telegram_bot import _deliver_view
        from services.telegram_views import BotView

        view = BotView("Menu", [])
        with (
            patch(
                "services.telegram_bot.edit_message_text",
                side_effect=TelegramApiError("message cannot be edited"),
            ),
            patch("services.telegram_bot.send_message") as send,
        ):
            _deliver_view("token", 10, view, message_id=20)

        send.assert_called_once()

    def test_client_section_views_render_actionable_summary(self) -> None:
        from services.telegram_client_summary import (
            CaseStep,
            CaseSummary,
            ClientSummary,
            ClientTask,
            DocumentSummary,
        )
        from services.telegram_views import (
            build_case_view,
            build_documents_view,
            build_tasks_view,
        )

        summary = ClientSummary(
            tasks=[ClientTask("upload", "Справка", "18.07", "urgent", "https://example.test/docs")],
            documents=DocumentSummary(pending_upload=1, in_review=2, approved=3, needs_fix=1),
            case=CaseSummary(
                steps=(CaseStep("Анкета", "completed"), CaseStep("Проверка", "active")),
                active_title="Проверка",
                updated_at="2026-07-12T10:00:00Z",
            ),
        )

        self.assertIn("Справка", build_tasks_view("ru", summary).text)
        self.assertIn("На проверке: 2", build_documents_view("ru", summary).text)
        self.assertIn("🔵 Проверка", build_case_view("ru", summary).text)

    def test_section_callback_selects_expected_view(self) -> None:
        from services.telegram_client_summary import ClientSummary
        from services.telegram_views import build_client_section_view

        summary = ClientSummary()

        self.assertTrue(build_client_section_view("nav:tasks", "ru", summary).text.startswith("✅"))
        self.assertTrue(build_client_section_view("nav:docs", "ru", summary).text.startswith("📄"))
        self.assertTrue(build_client_section_view("nav:case", "ru", summary).text.startswith("📍"))
        self.assertIsNone(build_client_section_view("nav:unknown", "ru", summary))


if __name__ == "__main__":
    unittest.main()
