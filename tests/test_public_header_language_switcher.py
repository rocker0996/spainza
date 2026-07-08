from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PublicHeaderLanguageSwitcherTest(unittest.TestCase):
    def test_public_headers_use_segmented_language_switcher(self):
        for language in ("ru", "en"):
            with self.subTest(language=language):
                html = (ROOT / "shared" / language / "header.html").read_text(encoding="utf-8")

                self.assertIn('aria-label="Language"', html)
                self.assertIn("bg-slate-100", html)
                self.assertIn("rounded-lg", html)
                self.assertIn('data-lang-switch="en"', html)
                self.assertIn('data-lang-switch="ru"', html)
                self.assertIn("bg-white shadow-sm text-primary-container", html)
                self.assertIn("text-slate-500 hover:text-primary-container", html)
                self.assertNotIn("<span>/</span>", html)

    def test_tailwind_scans_shared_layout_fragments(self):
        config = (ROOT / "tailwind.config.js").read_text(encoding="utf-8")

        self.assertIn("./shared/**/*.{html,js}", config)


if __name__ == "__main__":
    unittest.main()
