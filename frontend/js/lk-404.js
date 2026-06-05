/**
 * LK 404 page copy (i18n + document title).
 */
(function () {
  function t(key) {
    return window.LkI18n ? window.LkI18n.t(key) : key;
  }

  function applyCopy() {
    const textEl = document.getElementById("lk-not-found-text");
    const btnEl = document.getElementById("lk-not-found-button");
    const text =
      t("adminAudit.notFoundText") !== "adminAudit.notFoundText"
        ? t("adminAudit.notFoundText")
        : "Кажется, вы заблудились. Вот кнопка, которая вернёт вас на главную страницу.";
    const btnLabel =
      t("adminAudit.notFoundButton") !== "adminAudit.notFoundButton"
        ? t("adminAudit.notFoundButton")
        : "На главную";
    if (textEl) textEl.textContent = text;
    if (btnEl) btnEl.textContent = btnLabel;
    if (window.LkI18n) {
      window.LkI18n.applyDocument();
    }
  }

  function run() {
    applyCopy();
    document.querySelectorAll("[data-locale-btn]").forEach((btn) => {
      btn.addEventListener("click", () => {
        if (window.LkI18n) {
          window.LkI18n.setLocale(btn.getAttribute("data-locale-btn"));
        }
        applyCopy();
      });
    });
  }

  if (window.LkI18n) {
    run();
  } else {
    document.addEventListener("DOMContentLoaded", run);
  }
})();
