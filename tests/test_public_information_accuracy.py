import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class PublicInformationAccuracyTest(unittest.TestCase):
    def test_digital_nomad_thresholds_match_2026_smi_in_both_locales(self):
        ru = read("frontend/ru/index.html")
        en = read("frontend/en/index.html")

        for value in ("€34 188", "€12 820,50", "€4 273,50"):
            self.assertIn(value, ru)
        for value in ("€34 188", "€12 820.50", "€4 273.50"):
            self.assertIn(value, en)

        for page in (ru, en):
            for percentage in ("200%", "75%", "25%"):
                self.assertIn(percentage, page)
            self.assertNotIn("€2,646", page)
            self.assertNotIn("€993", page)
            self.assertNotIn("€331", page)

    def test_digital_nomad_qualification_lists_all_recognized_routes(self):
        ru = read("frontend/ru/index.html")
        en = read("frontend/en/index.html")

        for phrase in ("признанного университета", "профессионального образования", "бизнес-школы", "трёх лет"):
            self.assertIn(phrase, ru)
        for phrase in ("recognised university", "vocational training institution", "business school", "three years"):
            self.assertIn(phrase, en)

    def test_general_process_routes_to_the_competent_authority(self):
        ru_process = read("frontend/ru/process.html")
        en_process = read("frontend/en/process.html")
        ru_services = read("frontend/ru/services.html")
        en_services = read("frontend/en/services.html")

        for page in (ru_process, ru_services):
            for phrase in ("Закон 14/2013", "Extranjería", "консульство"):
                self.assertIn(phrase, page)
        for page in (en_process, en_services):
            for phrase in ("Law 14/2013", "Extranjería", "consulate"):
                self.assertIn(phrase, page)

        self.assertNotIn("иммиграционного законодательства UGE", ru_process)
        self.assertNotIn("current UGE immigration requirements", en_process)

    def test_all_legal_pages_show_the_effective_date(self):
        for locale, date_text in (("ru", "20 июля 2026 года"), ("en", "20 July 2026")):
            for name in ("terms-of-service", "privacy-policy", "cookie-policy"):
                with self.subTest(locale=locale, page=name):
                    self.assertIn(date_text, read(f"frontend/{locale}/{name}.html"))

    def test_cookie_policies_match_current_storage_implementation(self):
        for locale in ("ru", "en"):
            page = read(f"frontend/{locale}/cookie-policy.html")
            for key in (
                "access_token",
                "google_oauth_state",
                "currentUserProfile",
                "currentUserProfileSavedAt",
                "spainza.language",
                "userLocale",
                "spainza.cookieConsent.v1",
                "manager_invite_token",
                "token",
            ):
                with self.subTest(locale=locale, key=key):
                    self.assertIn(key, page)
            self.assertIn("7", page)
            self.assertIn("10", page)
            self.assertIn("HttpOnly", page)
            self.assertIn("SameSite", page)

        self.assertIn("после успешного", read("frontend/ru/cookie-policy.html"))
        self.assertIn("при отмене или ошибке", read("frontend/ru/cookie-policy.html"))
        self.assertIn("after successful", read("frontend/en/cookie-policy.html"))
        self.assertIn("cancelled or fails", read("frontend/en/cookie-policy.html"))

    def test_cookie_banner_does_not_offer_nonexistent_optional_analytics(self):
        banner = read("frontend/js/cookie-consent.js")

        self.assertNotIn("optional analytics", banner)
        self.assertNotIn("дополнительные помогают улучшать", banner)
        self.assertNotIn('accept: "Accept all"', banner)
        self.assertNotIn('accept: "Принять все"', banner)
        self.assertIn("necessary technologies", banner)
        self.assertIn("необходимые технологии", banner)


if __name__ == "__main__":
    unittest.main()
