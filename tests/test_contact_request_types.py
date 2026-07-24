import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ContactRequestTypesTest(unittest.TestCase):
    def test_request_types_are_localized_and_ordered(self):
        expected = {
            "ru": (
                "ВНЖ Цифрового кочевника",
                "ВНЖ для ведения бизнеса",
                "Воссоединение семьи",
                "Гражданство Испании",
                "Продление ВНЖ",
                "Другое",
            ),
            "en": (
                "Digital Nomad Residence Permit",
                "Business Residency",
                "Family Reunification",
                "Spanish Citizenship",
                "Residence Permit Renewal",
                "Other",
            ),
        }

        for locale, labels in expected.items():
            with self.subTest(locale=locale):
                page = (ROOT / f"frontend/{locale}/contact.html").read_text(
                    encoding="utf-8"
                )
                request_type_start = page.index(
                    "Тип запроса" if locale == "ru" else "Request Type"
                )
                select_end = page.index("</select>", request_type_start)
                request_type_select = page[request_type_start:select_end]

                actual_labels = tuple(
                    re.findall(r"<option>(.*?)</option>", request_type_select)
                )
                self.assertEqual(actual_labels, labels)


if __name__ == "__main__":
    unittest.main()
