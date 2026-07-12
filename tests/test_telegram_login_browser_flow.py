from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TelegramLoginBrowserFlowTest(unittest.TestCase):
    def test_login_keeps_origin_page_for_polling(self) -> None:
        source = (ROOT / "frontend/js/login.js").read_text(encoding="utf-8")

        self.assertNotIn("window.location.href = target;", source)
        self.assertIn('window.open("about:blank", "_blank")', source)
        self.assertIn("startTelegramAppLogin(botUsername, telegramWindow)", source)
        self.assertLess(
            source.index('window.open("about:blank", "_blank")'),
            source.index("startTelegramAppLogin(botUsername, telegramWindow)"),
        )
        self.assertIn("window.setInterval", source)

    def test_popup_block_fallback_is_localized(self) -> None:
        source = (ROOT / "frontend/js/login-i18n.js").read_text(encoding="utf-8")

        self.assertGreaterEqual(source.count('"login.telegramOpen"'), 2)


if __name__ == "__main__":
    unittest.main()
