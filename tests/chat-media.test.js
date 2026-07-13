const test = require("node:test");
const assert = require("node:assert/strict");

const {
  extractClipboardImageFiles,
  createImageViewerController,
} = require("../frontend/js/chat-media.js");

test("extractClipboardImageFiles returns image files and ignores other clipboard items", () => {
  const png = { name: "screenshot.png", type: "image/png" };
  const jpeg = { name: "photo.jpg", type: "image/jpeg" };
  const clipboardData = {
    items: [
      { kind: "string", type: "text/plain", getAsFile: () => null },
      { kind: "file", type: "application/pdf", getAsFile: () => ({ name: "doc.pdf" }) },
      { kind: "file", type: "image/png", getAsFile: () => png },
      { kind: "file", type: "image/jpeg", getAsFile: () => jpeg },
      { kind: "file", type: "image/webp", getAsFile: () => null },
    ],
  };

  assert.deepEqual(extractClipboardImageFiles(clipboardData), [png, jpeg]);
});

test("extractClipboardImageFiles tolerates missing clipboard data", () => {
  assert.deepEqual(extractClipboardImageFiles(null), []);
  assert.deepEqual(extractClipboardImageFiles({}), []);
});

test("image viewer controller opens with image data and clears source after close", async () => {
  const modal = { id: "chat-image-viewer" };
  const attributes = new Map();
  const image = {
    setAttribute(name, value) {
      attributes.set(name, value);
    },
    removeAttribute(name) {
      attributes.delete(name);
    },
  };
  const calls = [];
  const controller = createImageViewerController({
    modal,
    image,
    openModal(value) {
      calls.push(["open", value]);
    },
    async closeModal(value) {
      calls.push(["close", value]);
    },
  });

  controller.open({ src: "/api/messages/7/image", alt: "Фото в сообщении" });
  assert.equal(attributes.get("src"), "/api/messages/7/image");
  assert.equal(attributes.get("alt"), "Фото в сообщении");
  assert.deepEqual(calls, [["open", modal]]);

  await controller.close();
  assert.equal(attributes.has("src"), false);
  assert.deepEqual(calls, [["open", modal], ["close", modal]]);
});
