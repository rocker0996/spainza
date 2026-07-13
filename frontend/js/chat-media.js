(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) {
    module.exports = api;
  }
  root.ChatMedia = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  function extractClipboardImageFiles(clipboardData) {
    return Array.from(clipboardData?.items || [])
      .filter(
        (item) =>
          item && item.kind === "file" && String(item.type || "").startsWith("image/")
      )
      .map((item) => item.getAsFile())
      .filter(Boolean);
  }

  function createImageViewerController({ modal, image, openModal, closeModal }) {
    return {
      open({ src, alt }) {
        image.setAttribute("src", src);
        image.setAttribute("alt", alt || "");
        openModal(modal);
      },
      async close() {
        await closeModal(modal);
        image.removeAttribute("src");
      },
    };
  }

  return {
    extractClipboardImageFiles,
    createImageViewerController,
  };
});
