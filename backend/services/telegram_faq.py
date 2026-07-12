"""Curated bilingual FAQ content for the Telegram assistant."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FaqArticle:
    article_id: str
    category: str
    title_ru: str
    body_ru: str
    title_en: str
    body_en: str

    def title(self, locale: str) -> str:
        return self.title_en if locale == "en" else self.title_ru

    def body(self, locale: str) -> str:
        return self.body_en if locale == "en" else self.body_ru


FAQ_CATEGORIES = {
    "documents": ("📄 Документы", "📄 Documents"),
    "process": ("📍 Статусы и сроки", "📍 Statuses and timing"),
    "portal": ("💻 Личный кабинет", "💻 Client portal"),
}


def _article(article_id: str, category: str, title_ru: str, body_ru: str, title_en: str, body_en: str) -> FaqArticle:
    return FaqArticle(article_id, category, title_ru, body_ru, title_en, body_en)


FAQ_ARTICLES = {
    article.article_id: article
    for article in [
        _article(
            "doc_formats", "documents", "Какие форматы файлов подходят?",
            "Загружайте читаемые PDF, JPG или PNG. Один документ лучше сохранять одним файлом. Если страница размыта или обрезана, проверка может занять больше времени.",
            "Which file formats can I use?",
            "Upload clear PDF, JPG or PNG files. It is best to keep one document in one file. Blurred or cropped pages may delay review.",
        ),
        _article(
            "doc_rejected", "documents", "Что делать, если документ отклонён?",
            "Откройте комментарий к документу, исправьте указанную проблему и загрузите новую версию через личный кабинет. Старая версия сохранится в истории.",
            "What if my document was rejected?",
            "Open the document comment, fix the stated issue and upload a new version through the portal. The previous version remains in the history.",
        ),
        _article(
            "translation", "documents", "Нужен ли перевод?",
            "Требования зависят от типа документа и вашего кейса. Проверьте комментарий к запросу. Если язык или вид перевода не указан, задайте менеджеру вопрос по конкретному документу.",
            "Do I need a translation?",
            "Requirements depend on the document and your case. Check the request comment. If the language or translation type is not specified, ask your manager about that document.",
        ),
        _article(
            "apostille", "documents", "Нужен ли апостиль?",
            "Апостиль требуется не для каждого документа. Не оформляйте его только на основании общего ответа: проверьте запрос в кейсе или уточните у менеджера название документа и страну выдачи.",
            "Do I need an apostille?",
            "Not every document requires an apostille. Do not order one based only on general guidance: check the case request or tell your manager the document name and issuing country.",
        ),
        _article(
            "review_time", "process", "Сколько длится проверка?",
            "Срок зависит от объёма и типа материалов. Актуальный статус виден в разделе «Документы». Бот сообщит, когда документ будет одобрен или потребуется исправление.",
            "How long does review take?",
            "Timing depends on the amount and type of material. The current status is shown under Documents. The bot will notify you when a document is approved or needs changes.",
        ),
        _article(
            "case_status", "process", "Что означает статус кейса?",
            "Синий этап выполняется сейчас, галочкой отмечены завершённые этапы, серым — будущие. Если от вас требуется действие, оно появится в разделе «Что нужно сделать».",
            "What does my case status mean?",
            "The blue stage is in progress, checked stages are complete and grey stages are upcoming. If you need to act, it appears under What to do.",
        ),
        _article(
            "next_step", "process", "Что будет дальше?",
            "Откройте «Мой кейс»: там показан активный этап и последовательность следующих этапов. Точные даты отображаются только когда они добавлены командой Spainza.",
            "What happens next?",
            "Open My case to see the active stage and the upcoming sequence. Exact dates are shown only after the Spainza team adds them.",
        ),
        _article(
            "portal_access", "portal", "Как открыть личный кабинет?",
            "Нажмите кнопку перехода в любом разделе бота. Если сессия истекла, войдите снова через Telegram или email. Никому не передавайте код входа.",
            "How do I open the client portal?",
            "Use the portal button in any bot section. If your session expired, sign in again with Telegram or email. Never share a sign-in code.",
        ),
        _article(
            "upload_help", "portal", "Не получается загрузить файл",
            "Повторите загрузку при стабильном подключении. Если ошибка сохраняется, откройте сообщения по кнопке ниже и отправьте менеджеру текст ошибки.",
            "I cannot upload a file",
            "Retry the upload on a stable connection. If the error continues, open Messages using the button below and send the error text to your manager.",
        ),
    ]
}


def get_faq(locale: str, article_id: str) -> Optional[FaqArticle]:
    del locale
    return FAQ_ARTICLES.get(article_id)


def search_faq(locale: str, category: str) -> list[FaqArticle]:
    del locale
    return [article for article in FAQ_ARTICLES.values() if article.category == category]
