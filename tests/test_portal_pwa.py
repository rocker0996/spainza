import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class PortalPwaTest(unittest.TestCase):
    def test_login_and_portal_pages_reference_installable_app_assets(self):
        pages = [ROOT / "frontend" / "login.html"]
        pages.extend(sorted((ROOT / "frontend" / "lk").glob("*.html")))

        for page in pages:
            with self.subTest(page=page.relative_to(ROOT).as_posix()):
                html = page.read_text(encoding="utf-8")

                self.assertIn('rel="manifest" href="/frontend/app.webmanifest"', html)
                self.assertIn("/frontend/js/pwa.js", html)
                self.assertIn('name="apple-mobile-web-app-capable" content="yes"', html)

    def test_manifest_uses_site_icon_and_starts_in_client_portal(self):
        manifest = json.loads((ROOT / "frontend" / "app.webmanifest").read_text(encoding="utf-8"))

        self.assertEqual(manifest["name"], "Spainza Client Portal")
        self.assertEqual(manifest["start_url"], "/frontend/lk/dashboard.html")
        self.assertEqual(manifest["scope"], "/frontend/")
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["icons"][0]["src"], "/frontend/img/icon.png")

        icon_sources = {icon["src"] for icon in manifest["icons"]}
        self.assertIn("/frontend/img/app-icon-192.png", icon_sources)
        self.assertIn("/frontend/img/app-icon-512.png", icon_sources)
        self.assertTrue((ROOT / "frontend" / "img" / "app-icon-192.png").is_file())
        self.assertTrue((ROOT / "frontend" / "img" / "app-icon-512.png").is_file())

    def test_service_worker_precaches_portal_shell_assets(self):
        service_worker = (ROOT / "frontend" / "pwa-sw.js").read_text(encoding="utf-8")

        self.assertIn("/frontend/lk/dashboard.html", service_worker)
        self.assertIn("/frontend/login.html", service_worker)
        self.assertIn("/frontend/app.webmanifest", service_worker)
        self.assertIn('spainza-portal-shell-v2', service_worker)
        self.assertIn('/frontend/css/portal.css?v=2', service_worker)
        self.assertIn("/frontend/img/icon.png", service_worker)


if __name__ == "__main__":
    unittest.main()
