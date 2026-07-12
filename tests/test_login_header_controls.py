from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class LoginHeaderControlsTest(unittest.TestCase):
    def setUp(self):
        self.html = (ROOT / "frontend" / "login.html").read_text(encoding="utf-8")

    def test_login_page_has_no_home_navigation_controls(self):
        self.assertNotIn('id="login-back-home"', self.html)
        self.assertNotIn(">explore</span>", self.html)
        self.assertNotIn(">arrow_back</span>", self.html)
        self.assertNotIn('data-i18n="login.backHome"', self.html)
        self.assertIn('id="login-brand-home"', self.html)
        self.assertIn('href="/ru/index.html"', self.html)
        self.assertIn("pointer-events-none", self.html)
        self.assertIn("pointer-events-auto", self.html)
        self.assertIn(">Spainza</a>", self.html)

    def test_login_language_switcher_is_compact(self):
        self.assertIn('id="login-locale-switcher"', self.html)
        self.assertIn('id="login-card"', self.html)
        self.assertIn("absolute right-4 top-4", self.html)
        self.assertIn("z-20", self.html)
        self.assertIn("grid-cols-2", self.html)
        self.assertIn("w-[6.5rem]", self.html)
        self.assertIn("p-0.5", self.html)
        self.assertIn("h-7", self.html)
        self.assertIn("inline-flex", self.html)
        self.assertIn('aria-label="Language"', self.html)
        self.assertIn('data-locale-btn="ru"', self.html)
        self.assertIn('data-locale-btn="en"', self.html)
        self.assertIn(">RU</button>", self.html)
        self.assertIn(">EN</button>", self.html)
        self.assertIn('/frontend/css/portal.css?v=2', self.html)
        self.assertIn('/frontend/js/login-i18n.js?v=13', self.html)
        self.assertNotIn('data-i18n="common.langRu"', self.html)
        self.assertNotIn('data-i18n="common.langEn"', self.html)


if __name__ == "__main__":
    unittest.main()
