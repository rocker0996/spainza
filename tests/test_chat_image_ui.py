import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ChatImageUiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (ROOT / "frontend" / "lk" / "messages.html").read_text(encoding="utf-8-sig")
        cls.chat_js = (ROOT / "frontend" / "js" / "chat.js").read_text(encoding="utf-8")
        cls.i18n_js = (ROOT / "frontend" / "js" / "lk-i18n.js").read_text(encoding="utf-8")

    def test_media_helper_loads_before_chat(self):
        media_index = self.html.index("../js/chat-media.js")
        chat_index = self.html.index("../js/chat.js")
        self.assertLess(media_index, chat_index)

    def test_page_contains_accessible_branded_image_viewer(self):
        self.assertIn('id="chat-image-viewer"', self.html)
        self.assertIn('role="dialog"', self.html)
        self.assertIn('aria-modal="true"', self.html)
        self.assertIn('aria-labelledby="chat-image-viewer-title"', self.html)
        self.assertIn('id="chat-image-viewer-image"', self.html)
        self.assertIn('id="chat-image-viewer-close"', self.html)
        self.assertIn("chat-image-viewer__panel", self.html)
        self.assertEqual(self.i18n_js.count('"chat.imageViewerTitle"'), 2)
        self.assertEqual(self.i18n_js.count('"chat.openImage"'), 2)
        self.assertEqual(self.i18n_js.count('"chat.closeImage"'), 2)

    def test_composer_routes_clipboard_images_to_attachment_queue(self):
        self.assertIn('byId.messageInput.addEventListener("paste"', self.chat_js)
        self.assertIn("ChatMedia.extractClipboardImageFiles(event.clipboardData)", self.chat_js)
        self.assertIn("queueAttachments(imageFiles)", self.chat_js)
        self.assertIn("event.preventDefault()", self.chat_js)

    def test_message_images_open_viewer_without_opening_message_actions(self):
        self.assertIn("chat-image-viewer-trigger", self.chat_js)
        self.assertIn('data-chat-image-src=', self.chat_js)
        self.assertIn('closest(".chat-image-viewer-trigger")', self.chat_js)
        self.assertIn("imageViewer.open", self.chat_js)

    def test_viewer_supports_close_button_backdrop_and_escape(self):
        self.assertIn('chatImageViewerClose.addEventListener("click"', self.chat_js)
        self.assertIn('chatImageViewer.addEventListener("click"', self.chat_js)
        self.assertIn('chatImageViewer.classList.contains("is-open")', self.chat_js)
        self.assertIn("imageViewer.close()", self.chat_js)


if __name__ == "__main__":
    unittest.main()
