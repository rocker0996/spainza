import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


class NomadPagesTest(unittest.TestCase):
    def test_nomad_pages_include_required_sections_and_links(self):
        expected = {
            "ru": (
                "ВНЖ Digital Nomad Испании",
                "Ваш кейс проходит 4 уровня проверки",
                "Что именно делает Spainza",
                "Почему дела получают запросы или отказы",
                "Полное сопровождение Digital Nomad",
            ),
            "en": (
                "Spain Digital Nomad residence permit",
                "Your case passes 4 levels of review",
                "What exactly does Spainza do",
                "Why applications receive requests or refusals",
                "Complete Digital Nomad support",
            ),
        }

        for locale, phrases in expected.items():
            with self.subTest(locale=locale):
                page = read(f"frontend/{locale}/nomad.html")
                self.assertIn("DIGITAL NOMAD RESIDENCE · SPAIN · 2026", page)
                self.assertIn('href="./nomad-case.html"', page)
                self.assertIn('href="./contact.html?service=nomad"', page)
                self.assertIn("€1 600", page)
                self.assertNotIn('href="#"', page)
                self.assertNotIn('"@type": "FAQPage"', page)
                for phrase in phrases:
                    self.assertIn(phrase, page)

    def test_case_pages_are_localized_and_have_replaceable_document_images(self):
        expected = {
            "ru": ("Структура реального кейса", "Все данные обезличены"),
            "en": ("Real case structure", "All data is anonymised"),
        }
        for locale, phrases in expected.items():
            with self.subTest(locale=locale):
                page = read(f"frontend/{locale}/nomad-case.html")
                for name in ("employment-contract", "experience-proof", "bank-evidence"):
                    self.assertIn(f"/frontend/img/nomad-case/{name}.webp", page)
                self.assertIn('"@type":"Article"', page)
                self.assertIn('href="./contact.html?service=nomad"', page)
                self.assertNotIn('href="#"', page)
                for phrase in phrases:
                    self.assertIn(phrase, page)

    def test_home_pages_include_visible_faq_and_matching_schema(self):
        expected_questions = {
            "ru": (
                "Как получить ВНЖ Digital Nomad в Испании в 2026 году?",
                "Можно ли подать документы, находясь в Испании по туристической визе другого государства Шенген?",
                "Можно ли работать с испанскими клиентами?",
            ),
            "en": (
                "How can I obtain Spain’s Digital Nomad residence permit in 2026?",
                "Can I apply while in Spain on a tourist visa issued by another Schengen country?",
                "Can I work with Spanish clients?",
            ),
        }

        for locale, questions in expected_questions.items():
            with self.subTest(locale=locale):
                page = read(f"frontend/{locale}/index.html")
                self.assertEqual(page.count("<details"), 9)
                self.assertIn('"@type":"FAQPage"', page)
                for value in ("200%", "75%", "25%"):
                    self.assertIn(value, page)
                for question in questions:
                    self.assertIn(question, page)

    def test_public_page_registries_include_case_page(self):
        self.assertIn('"nomad-case.html"', read("tools/bootstrap_server.py"))
        self.assertIn('"nomad-case.html"', read("tools/remote_deploy.py"))
        sitemap = read("sitemap.xml")
        self.assertIn("https://spainza.com/ru/nomad-case.html", sitemap)
        self.assertIn("https://spainza.com/en/nomad-case.html", sitemap)

    def test_home_faq_matches_site_width_and_has_animated_active_state(self):
        for locale in ("ru", "en"):
            with self.subTest(locale=locale):
                page = read(f"frontend/{locale}/index.html")
                self.assertIn('id="faq"', page)
                self.assertIn('id="faq" class="py-16 sm:py-24 bg-surface-container-low"', page)
                self.assertIn('max-w-7xl mx-auto', page[page.index('id="faq"'):])
                self.assertEqual(page.count('class="faq-item '), 9)
                self.assertIn(".faq-item::details-content", page)
                self.assertIn(".faq-item[open]", page)
                self.assertIn("transition:", page)

    def test_nomad_revision_removes_rejected_copy_and_aligns_content(self):
        ru = read("frontend/ru/nomad.html")
        en = read("frontend/en/nomad.html")

        for page in (ru, en):
            self.assertNotIn("max-w-4xl text-lg", page)
            self.assertNotIn("bg-white/10 rounded-2xl p-7", page)
            self.assertNotIn("Core programme criteria", page)
            self.assertNotIn("The final fee depends", page)
            self.assertIn("оформления&nbsp;TIE" if page is ru else "and&nbsp;TIE registration", page)

        for phrase in (
            "Срок рассмотрения отсчитывается",
            "Проверяем то, что влияет на решение",
            "Не общие преимущества, а доказательства вашего права",
            "Базовые критерии программы",
            "Финальная стоимость зависит",
            "Начните с оценки, а не со сбора документов",
        ):
            self.assertNotIn(phrase, ru)

        self.assertIn("Готовы приступить к процессу?", ru)
        self.assertIn("Ready to start the process?", en)


if __name__ == "__main__":
    unittest.main()
