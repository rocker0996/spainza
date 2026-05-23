/**
 * Login / register page i18n (ru / en).
 */
(function (global) {
  "use strict";

  var LOCALE_KEY = "spainza.language";

  var STRINGS = {
    ru: {
      "login.pageTitle": "Вход и регистрация — Spainza",
      "login.backHome": "На главную",
      "login.welcome": "Добро пожаловать",
      "login.lead": "Войдите в систему или создайте аккаунт, чтобы продолжить.",
      "login.tabLogin": "Вход",
      "login.tabRegister": "Регистрация",
      "login.email": "Электронная почта",
      "login.password": "Пароль",
      "login.forgotPassword": "Забыли пароль?",
      "login.confirmPassword": "Повторите пароль",
      "login.submitLogin": "Войти",
      "login.submitRegister": "Зарегистрироваться",
      "login.orContinue": "Или продолжите с",
      "login.togglePasswordShow": "Показать пароль",
      "login.togglePasswordHide": "Скрыть пароль",
      "login.passwordMismatch": "Пароли не совпадают",
      "login.apiUnreachable":
        "Не удалось подключиться к API. Проверьте backend (например, http://localhost:5000)",
      "login.requestError": "Ошибка запроса",
      "login.genericError": "Ошибка",
      "login.registerSuccessWithId":
        "Регистрация успешна. Ваш номер клиента: {id}. Теперь войдите.",
      "login.registerSuccess": "Регистрация успешна. Теперь войдите.",
      "common.interfaceLanguage": "Язык интерфейса",
      "common.langRu": "Русский",
      "common.langEn": "English",
    },
    en: {
      "login.pageTitle": "Sign in & register — Spainza",
      "login.backHome": "Back to home",
      "login.welcome": "Welcome back",
      "login.lead": "Log in or create an account to continue.",
      "login.tabLogin": "Login",
      "login.tabRegister": "Register",
      "login.email": "Email address",
      "login.password": "Password",
      "login.forgotPassword": "Forgot password?",
      "login.confirmPassword": "Confirm password",
      "login.submitLogin": "Log in",
      "login.submitRegister": "Create account",
      "login.orContinue": "Or continue with",
      "login.togglePasswordShow": "Show password",
      "login.togglePasswordHide": "Hide password",
      "login.passwordMismatch": "Passwords do not match",
      "login.apiUnreachable":
        "Cannot reach the API. Check that the backend is running (e.g. http://localhost:5000)",
      "login.requestError": "Request error",
      "login.genericError": "Error",
      "login.registerSuccessWithId":
        "Registration successful. Your client ID: {id}. You can sign in now.",
      "login.registerSuccess": "Registration successful. You can sign in now.",
      "common.interfaceLanguage": "Interface language",
      "common.langRu": "Russian",
      "common.langEn": "English",
    },
  };

  function normalizeLocale(raw) {
    var code = String(raw || "")
      .trim()
      .toLowerCase()
      .split("-")[0];
    return code === "en" ? "en" : code === "ru" ? "ru" : null;
  }

  function readStoredLocale() {
    try {
      return normalizeLocale(global.localStorage.getItem(LOCALE_KEY));
    } catch (_e) {
      return null;
    }
  }

  function getLocale() {
    var stored = readStoredLocale();
    if (stored) return stored;

    var fromUrl = null;
    try {
      fromUrl = normalizeLocale(
        new URLSearchParams(global.location.search).get("lang")
      );
    } catch (_e) {
      /* ignore */
    }
    if (fromUrl) return fromUrl;

    var path = String(global.location.pathname || "");
    if (/\/frontend\/en\//i.test(path)) return "en";
    if (/\/frontend\/ru\//i.test(path)) return "ru";

    var htmlLang = normalizeLocale(global.document.documentElement.lang);
    return htmlLang || "ru";
  }

  function setLocale(locale) {
    var next = locale === "en" ? "en" : "ru";
    try {
      global.localStorage.setItem(LOCALE_KEY, next);
    } catch (_e) {
      /* ignore */
    }
    try {
      global.localStorage.setItem("userLocale", next);
    } catch (_e2) {
      /* ignore */
    }
    try {
      var url = new URL(global.location.href);
      url.searchParams.set("lang", next);
      global.history.replaceState({}, "", url);
    } catch (_eUrl) {
      /* ignore */
    }

    applyDocument();
    paintLocaleButtons();
    try {
      global.dispatchEvent(
        new CustomEvent("login-locale-change", { detail: { locale: next } })
      );
    } catch (_e3) {
      /* ignore */
    }
    return next;
  }

  function interpolate(template, params) {
    if (!params || typeof template !== "string") return template;
    return template.replace(/\{(\w+)\}/g, function (_m, key) {
      return params[key] != null ? String(params[key]) : "";
    });
  }

  function t(key, params) {
    var loc = getLocale();
    var bucket = STRINGS[loc] || STRINGS.ru;
    var value = bucket[key];
    if (value == null) value = STRINGS.ru[key];
    if (value == null) return key;
    return interpolate(value, params);
  }

  function applyDocument(root) {
    root = root || global.document;
    if (!root || !root.querySelectorAll) return;

    root.querySelectorAll("[data-i18n]").forEach(function (el) {
      var key = el.getAttribute("data-i18n");
      if (!key) return;
      el.textContent = t(key);
    });

    root.querySelectorAll("[data-i18n-placeholder]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-placeholder");
      if (!key) return;
      el.setAttribute("placeholder", t(key));
    });

    root.querySelectorAll("[data-i18n-aria]").forEach(function (el) {
      var key = el.getAttribute("data-i18n-aria");
      if (!key) return;
      el.setAttribute("aria-label", t(key));
    });

    var html = root.documentElement || root;
    if (html && html.setAttribute) {
      html.setAttribute("lang", getLocale());
    }

    var titleEl = root.querySelector("title[data-i18n]");
    if (titleEl) {
      titleEl.textContent = t(titleEl.getAttribute("data-i18n"));
    }

    var homeHref = homeUrl();
    var homeLink = root.getElementById("login-back-home");
    if (homeLink) {
      homeLink.setAttribute("href", homeHref);
    }
    var forgotLink = root.getElementById("forgot-password-link");
    if (forgotLink) {
      forgotLink.setAttribute("href", homeHref);
    }
  }

  function homeUrl() {
    var en = getLocale() === "en";
    if (global.location.protocol === "file:") {
      return en ? "./en/index.html" : "./ru/index.html";
    }
    return en ? "/frontend/en/index.html" : "/frontend/ru/index.html";
  }

  var localeActiveClass =
    "flex-1 py-2 rounded-lg text-xs font-bold bg-white shadow-sm text-primary transition-colors";
  var localeInactiveClass =
    "flex-1 py-2 rounded-lg text-xs font-bold text-slate-500 hover:text-primary transition-colors";

  function paintLocaleButtons() {
    var root = global.document.getElementById("login-locale-switcher");
    if (!root) return;
    var active = getLocale();
    root.querySelectorAll("[data-locale-btn]").forEach(function (btn) {
      var lang = btn.getAttribute("data-locale-btn");
      btn.className = lang === active ? localeActiveClass : localeInactiveClass;
    });
  }

  function initLangSwitcher() {
    var root = global.document.getElementById("login-locale-switcher");
    if (!root || root.dataset.bound === "1") return;
    root.dataset.bound = "1";

    root.addEventListener("click", function (event) {
      var btn = event.target.closest("[data-locale-btn]");
      if (!btn || !root.contains(btn)) return;
      var lang = btn.getAttribute("data-locale-btn");
      if (!lang) return;
      var next = lang === "en" ? "en" : "ru";
      if (next === getLocale()) return;
      setLocale(next);
    });

    paintLocaleButtons();
    global.addEventListener("login-locale-change", paintLocaleButtons);
  }

  global.LoginI18n = {
    getLocale: getLocale,
    setLocale: setLocale,
    t: t,
    applyDocument: applyDocument,
    homeUrl: homeUrl,
    initLangSwitcher: initLangSwitcher,
    paintLocaleButtons: paintLocaleButtons,
  };
})(typeof window !== "undefined" ? window : this);
