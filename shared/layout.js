(function () {
  var LANGUAGE_STORAGE_KEY = "spainza.language";
  var SUPPORTED_LANGUAGES = { ru: true, en: true };
  var EN_PAGES = {
    "index.html": true,
    "contact.html": true,
    "process.html": true,
    "services.html": true,
  };

  function normalizeLanguage(raw) {
    if (!raw || typeof raw !== "string") return null;
    var code = raw.toLowerCase().split("-")[0];
    return SUPPORTED_LANGUAGES[code] ? code : null;
  }

  function readStoredLanguage() {
    try {
      return normalizeLanguage(window.localStorage.getItem(LANGUAGE_STORAGE_KEY));
    } catch (_) {
      return null;
    }
  }

  function storeLanguage(language) {
    try {
      window.localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
    } catch (_) {
      // Ignore storage errors (private mode / denied storage).
    }
  }

  function detectBrowserLanguage() {
    var candidates = [];
    if (Array.isArray(navigator.languages)) {
      candidates = candidates.concat(navigator.languages);
    }
    if (navigator.language) {
      candidates.push(navigator.language);
    }

    for (var i = 0; i < candidates.length; i += 1) {
      var normalized = normalizeLanguage(candidates[i]);
      if (normalized) return normalized;
    }
    return null;
  }

  function resolveLanguageCode() {
    var fromStorage = readStoredLanguage();
    if (fromStorage) return fromStorage;

    var fromBrowser = detectBrowserLanguage();
    if (fromBrowser) return fromBrowser;

    var fromHtml = normalizeLanguage(document.documentElement.lang);
    return fromHtml || "ru";
  }

  function getLocalizedPageName(pathname) {
    var match = pathname.match(/\/frontend\/(?:ru|en)\/([^/?#]+)$/i);
    return match ? match[1].toLowerCase() : null;
  }

  function getLanguageFromPath(pathname) {
    var match = pathname.match(/\/frontend\/(ru|en)(?:\/|$)/i);
    return match ? match[1].toLowerCase() : null;
  }

  function getLocalizedPath(pathname, targetLanguage) {
    if (!/\/frontend\//i.test(pathname)) return null;

    var currentLanguage = getLanguageFromPath(pathname);
    if (currentLanguage) {
      return pathname.replace(/\/frontend\/(?:ru|en)(?=\/|$)/i, "/frontend/" + targetLanguage);
    }

    if (/\/frontend\/?(?:index\.html)?$/i.test(pathname)) {
      return pathname.replace(/\/frontend\/?(?:index\.html)?$/i, "/frontend/" + targetLanguage + "/index.html");
    }

    return null;
  }

  function shouldRedirectToLanguage(preferredLanguage) {
    var pathname = window.location.pathname;
    if (!/\/frontend\//i.test(pathname)) return null;

    var currentLanguage = getLanguageFromPath(pathname);
    var nextPath = getLocalizedPath(pathname, preferredLanguage);
    if (!nextPath || nextPath === pathname) return null;

    if (preferredLanguage === "en") {
      var pageName = getLocalizedPageName(pathname) || "index.html";
      if (!EN_PAGES[pageName]) return null;
    }

    if (currentLanguage && currentLanguage === preferredLanguage) return null;
    return nextPath;
  }

  function redirectToLanguage(targetLanguage) {
    var pathname = window.location.pathname;
    var nextPath = getLocalizedPath(pathname, targetLanguage);
    if (targetLanguage === "en") {
      var pageName = getLocalizedPageName(pathname) || "index.html";
      if (!EN_PAGES[pageName]) {
        nextPath = getLocalizedPath(pathname.replace(/\/(?:ru|en)\/[^/?#]+$/i, "/index.html"), "en");
      }
    }
    if (!nextPath) {
      nextPath = getLocalizedPath(pathname, targetLanguage) || "/frontend/" + targetLanguage + "/index.html";
    }
    window.location.assign(nextPath + window.location.search + window.location.hash);
  }

  function initLanguageSwitcher(language) {
    document.querySelectorAll("[data-lang-switch]").forEach(function (link) {
      var target = normalizeLanguage(link.getAttribute("data-lang-switch"));
      if (!target) return;

      var activeClass = "text-blue-600";
      var inactiveClass = "text-slate-500";
      link.classList.toggle(activeClass, target === language);
      link.classList.toggle(inactiveClass, target !== language);

      link.addEventListener("click", function (event) {
        event.preventDefault();
        storeLanguage(target);
        if (target === language) return;
        redirectToLanguage(target);
      });
    });
  }

  function initMobileNav() {
    var nav = document.querySelector("details.mobile-nav");
    if (!nav || nav.dataset.bound === "true") return;
    nav.dataset.bound = "true";

    document.addEventListener("click", function (e) {
      if (!nav.open) return;
      if (!nav.contains(e.target)) nav.removeAttribute("open");
    });

    nav.querySelectorAll("a").forEach(function (a) {
      a.addEventListener("click", function () {
        nav.removeAttribute("open");
      });
    });
  }

  function loadCookieConsent() {
    if (window.__spainzaCookieConsentLoaded || document.querySelector('script[src*="cookie-consent.js"]')) {
      return;
    }

    var script = document.createElement("script");
    script.defer = true;
    script.src = window.location.protocol === "file:"
      ? new URL("../frontend/js/cookie-consent.js", baseUrls[0]).href
      : "/frontend/js/cookie-consent.js";
    document.body.appendChild(script);
  }

  function uniq(items) {
    var seen = {};
    var result = [];
    for (var i = 0; i < items.length; i += 1) {
      var value = items[i];
      if (!value || seen[value]) continue;
      seen[value] = true;
      result.push(value);
    }
    return result;
  }

  function getBaseUrls() {
    var urls = [];
    var script =
      document.currentScript ||
      document.querySelector('script[src*="shared/layout.js"]');

    if (script && script.src) {
      try {
        urls.push(new URL(".", script.src).href);
      } catch (_) {
        // Ignore malformed script URL and continue with fallbacks.
      }
    }

    if (window.location.protocol !== "file:") {
      urls.push(window.location.origin + "/shared/");
    }
    urls.push("/shared/");
    urls.push("shared/");

    return uniq(urls);
  }

  function shouldLoad(area) {
    var value = document.body.dataset["layout" + area];
    return value !== "false";
  }

  function getOrCreateTarget(type) {
    var id = type === "Header" ? "site-header" : "site-footer";
    var tag = type.toLowerCase();
    var target = document.getElementById(id) || document.querySelector(tag);
    if (target) return target;

    var placeholder = document.createElement("div");
    placeholder.id = id;

    if (type === "Header") {
      document.body.insertBefore(placeholder, document.body.firstChild);
    } else {
      document.body.appendChild(placeholder);
    }
    return placeholder;
  }

  function fetchTemplate(baseUrls, candidates) {
    if (!baseUrls.length || !candidates.length) {
      return Promise.reject(new Error("No template"));
    }

    var currentBase = baseUrls[0];
    var currentCandidate = candidates[0];
    var url = new URL(currentCandidate, currentBase).href;

    return fetch(url)
      .then(function (res) {
        if (!res.ok) throw new Error("Failed to load " + url);
        return res.text();
      })
      .catch(function () {
        var nextCandidates = candidates.slice(1);
        if (nextCandidates.length) {
          return fetchTemplate([currentBase], nextCandidates);
        }
        return fetchTemplate(baseUrls.slice(1), candidates);
      });
  }

  function loadArea(type, fileName, baseUrls, language) {
    if (!shouldLoad(type)) return Promise.resolve();

    var target = getOrCreateTarget(type);
    var candidates = [language + "/" + fileName, "ru/" + fileName, fileName];

    return fetchTemplate(baseUrls, candidates)
      .then(function (html) {
        target.outerHTML = html;
      })
      .catch(function (error) {
        console.warn("[layout] Failed to load " + type + " template", error);
        // Keep original markup as fallback if loading fails.
      });
  }

  var baseUrls = getBaseUrls();
  var language = resolveLanguageCode();
  document.documentElement.lang = language;
  storeLanguage(language);

  var redirectPath = shouldRedirectToLanguage(language);
  if (redirectPath) {
    window.location.replace(redirectPath + window.location.search + window.location.hash);
    return;
  }

  Promise.all([
    loadArea("Header", "header.html", baseUrls, language),
    loadArea("Footer", "footer.html", baseUrls, language),
  ]).finally(function () {
    initMobileNav();
    initLanguageSwitcher(language);
    loadCookieConsent();
  });
})();
