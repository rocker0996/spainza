(function () {
  var STORAGE_KEY = "spainza.cookieConsent.v1";
  var BANNER_ID = "spainza-cookie-consent";

  if (window.__spainzaCookieConsentLoaded) return;
  window.__spainzaCookieConsentLoaded = true;

  function hasConsent() {
    try {
      return Boolean(window.localStorage.getItem(STORAGE_KEY));
    } catch (_) {
      return false;
    }
  }

  function saveConsent(value) {
    try {
      window.localStorage.setItem(
        STORAGE_KEY,
        JSON.stringify({
          value: value,
          savedAt: new Date().toISOString(),
        })
      );
    } catch (_) {
      // The banner will still close even if storage is unavailable.
    }
  }

  function getLanguage() {
    var params = new URLSearchParams(window.location.search || "");
    var fromQuery = params.get("lang");
    if (fromQuery === "en" || fromQuery === "ru") return fromQuery;

    var path = window.location.pathname || "";
    if (/\/en(?:\/|$)/i.test(path)) return "en";
    if (/\/ru(?:\/|$)/i.test(path)) return "ru";

    try {
      var lkLocale = window.localStorage.getItem("userLocale");
      if (lkLocale === "en" || lkLocale === "ru") return lkLocale;
      var siteLocale = window.localStorage.getItem("spainza.language");
      if (siteLocale === "en" || siteLocale === "ru") return siteLocale;
    } catch (_) {
      // Ignore storage errors.
    }

    return (document.documentElement.lang || "").toLowerCase().slice(0, 2) === "en"
      ? "en"
      : "ru";
  }

  function getPolicyHref(language) {
    if (window.location.protocol === "file:") {
      var script = document.currentScript || document.querySelector('script[src*="cookie-consent.js"]');
      if (script && script.src) {
        try {
          return new URL("../" + language + "/cookie-policy.html", script.src).href;
        } catch (_) {
          return "../" + language + "/cookie-policy.html";
        }
      }
    }
    return "/frontend/" + language + "/cookie-policy.html";
  }

  function text(language) {
    if (language === "en") {
      return {
        eyebrow: "Privacy settings",
        title: "Cookies make the service smoother",
        body:
          "We use essential cookies for login and security, and optional analytics to improve Spainza. You can accept all cookies or keep only the necessary ones.",
        accept: "Accept all",
        necessary: "Necessary only",
        details: "Cookie policy",
        close: "Close cookie notice",
      };
    }
    return {
      eyebrow: "Настройки приватности",
      title: "Мы используем cookies",
      body:
        "Нужные cookies помогают входить в личный кабинет и защищать сессию, а дополнительные помогают улучшать Spainza. Можно принять все или оставить только необходимые.",
      accept: "Принять все",
      necessary: "Только необходимые",
      details: "Политика cookies",
      close: "Закрыть уведомление о cookies",
    };
  }

  function ensureStyles() {
    if (document.getElementById("spainza-cookie-consent-style")) return;

    var style = document.createElement("style");
    style.id = "spainza-cookie-consent-style";
    style.textContent = [
      ".spainza-cookie{position:fixed;left:0;right:0;bottom:0;z-index:2147483000;padding:16px;pointer-events:none;font-family:Inter,Manrope,system-ui,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}",
      ".spainza-cookie__panel{pointer-events:auto;width:min(1120px,100%);margin:0 auto;display:grid;grid-template-columns:auto 1fr auto;gap:18px;align-items:center;padding:18px;border:1px solid rgba(255,255,255,.2);border-radius:22px;background:linear-gradient(135deg,rgba(13,18,31,.96),rgba(21,29,48,.93));color:#fff;box-shadow:0 24px 70px rgba(2,8,23,.35);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px)}",
      ".spainza-cookie__icon{width:48px;height:48px;border-radius:16px;display:grid;place-items:center;background:linear-gradient(135deg,#0052ff,#7dd3fc);box-shadow:0 12px 28px rgba(0,82,255,.35);font-size:25px;line-height:1}",
      ".spainza-cookie__eyebrow{margin:0 0 4px;color:#9cc3ff;font-size:11px;font-weight:800;letter-spacing:.08em;text-transform:uppercase}",
      ".spainza-cookie__title{margin:0;color:#fff;font-size:18px;line-height:1.2;font-weight:800;letter-spacing:0}",
      ".spainza-cookie__body{max-width:680px;margin:6px 0 0;color:rgba(239,246,255,.82);font-size:14px;line-height:1.55}",
      ".spainza-cookie__actions{display:flex;align-items:center;gap:10px;flex-wrap:wrap;justify-content:flex-end}",
      ".spainza-cookie__button{min-height:42px;border:0;border-radius:999px;padding:0 18px;font-size:13px;font-weight:800;white-space:nowrap;transition:transform .18s ease,box-shadow .18s ease,background .18s ease;color:#fff}",
      ".spainza-cookie__button:hover{transform:translateY(-1px)}",
      ".spainza-cookie__button--primary{background:#0052ff;box-shadow:0 12px 24px rgba(0,82,255,.32)}",
      ".spainza-cookie__button--secondary{background:rgba(255,255,255,.1);box-shadow:inset 0 0 0 1px rgba(255,255,255,.16)}",
      ".spainza-cookie__link{color:#bfdbfe;font-size:13px;font-weight:700;text-decoration:none;white-space:nowrap}",
      ".spainza-cookie__link:hover{color:#fff;text-decoration:underline}",
      ".spainza-cookie--hidden{opacity:0;transform:translateY(18px);transition:opacity .2s ease,transform .2s ease}",
      "@media (max-width:760px){.spainza-cookie{padding:10px}.spainza-cookie__panel{grid-template-columns:1fr;gap:12px;border-radius:18px;padding:16px}.spainza-cookie__icon{width:42px;height:42px;border-radius:14px}.spainza-cookie__actions{justify-content:stretch}.spainza-cookie__button{flex:1 1 150px}.spainza-cookie__link{width:100%;text-align:center}}",
    ].join("");
    document.head.appendChild(style);
  }

  function closeBanner(banner, value) {
    saveConsent(value);
    banner.classList.add("spainza-cookie--hidden");
    window.setTimeout(function () {
      banner.remove();
    }, 220);
  }

  function render() {
    if (!document.body || hasConsent() || document.getElementById(BANNER_ID)) return;

    var language = getLanguage();
    var copy = text(language);
    ensureStyles();

    var banner = document.createElement("aside");
    banner.id = BANNER_ID;
    banner.className = "spainza-cookie";
    banner.setAttribute("role", "dialog");
    banner.setAttribute("aria-live", "polite");
    banner.setAttribute("aria-label", copy.title);
    banner.innerHTML =
      '<div class="spainza-cookie__panel">' +
      '<div class="spainza-cookie__icon" aria-hidden="true">✓</div>' +
      "<div>" +
      '<p class="spainza-cookie__eyebrow">' + copy.eyebrow + "</p>" +
      '<h2 class="spainza-cookie__title">' + copy.title + "</h2>" +
      '<p class="spainza-cookie__body">' + copy.body + "</p>" +
      "</div>" +
      '<div class="spainza-cookie__actions">' +
      '<button class="spainza-cookie__button spainza-cookie__button--primary" type="button" data-cookie-choice="all">' + copy.accept + "</button>" +
      '<button class="spainza-cookie__button spainza-cookie__button--secondary" type="button" data-cookie-choice="necessary">' + copy.necessary + "</button>" +
      '<a class="spainza-cookie__link" href="' + getPolicyHref(language) + '">' + copy.details + "</a>" +
      "</div>" +
      "</div>";

    banner.querySelectorAll("[data-cookie-choice]").forEach(function (button) {
      button.addEventListener("click", function () {
        closeBanner(banner, button.getAttribute("data-cookie-choice") || "necessary");
      });
    });

    document.body.appendChild(banner);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", render, { once: true });
  } else {
    render();
  }
})();
