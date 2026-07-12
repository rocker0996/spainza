from __future__ import annotations

from pathlib import Path
import sys
import unittest


BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class TelegramFaqTest(unittest.TestCase):
    def test_every_article_has_complete_ru_and_en_copy(self) -> None:
        from services.telegram_faq import FAQ_ARTICLES

        self.assertGreaterEqual(len(FAQ_ARTICLES), 8)
        for article in FAQ_ARTICLES.values():
            self.assertTrue(article.title_ru)
            self.assertTrue(article.body_ru)
            self.assertTrue(article.title_en)
            self.assertTrue(article.body_en)

    def test_callback_identifiers_fit_telegram_limit(self) -> None:
        from services.telegram_faq import FAQ_ARTICLES

        for article_id in FAQ_ARTICLES:
            self.assertLessEqual(len(f"faq:{article_id}".encode("utf-8")), 64)

    def test_search_returns_only_selected_category(self) -> None:
        from services.telegram_faq import search_faq

        articles = search_faq("ru", "documents")

        self.assertTrue(articles)
        self.assertEqual({article.category for article in articles}, {"documents"})

    def test_article_view_offers_feedback_and_manager_question(self) -> None:
        from services.telegram_views import build_faq_view

        view = build_faq_view("ru", "doc_rejected")
        callbacks = [button.callback_data for row in view.rows for button in row]

        self.assertIn("faq:helped:doc_rejected", callbacks)
        self.assertIn("ask:start:documents", callbacks)

    def test_guest_keyboard_exposes_faq(self) -> None:
        from services.telegram_bot import _guest_menu_markup

        labels = [button["text"] for row in _guest_menu_markup(True)["keyboard"] for button in row]

        self.assertIn("📚 Частые вопросы", labels)


if __name__ == "__main__":
    unittest.main()
