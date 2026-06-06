(function () {
  "use strict";

  function t(key, params) {
    return window.LoginI18n ? window.LoginI18n.t(key, params) : key;
  }

  const loginTab = document.getElementById("tab-login");
  const registerTab = document.getElementById("tab-register");
  const form = document.getElementById("auth-form");
  const submitBtn = document.getElementById("submit-btn");
  const errorBox = document.getElementById("auth-error");
  const successBox = document.getElementById("auth-success");
  const emailInput = document.getElementById("email");
  const passwordInput = document.getElementById("password");
  const passwordToggleBtn = document.getElementById("password-toggle");
  const passwordToggleIcon = document.getElementById("password-toggle-icon");
  const forgotPasswordLink = document.getElementById("forgot-password-link");
  const backToLoginLink = document.getElementById("back-to-login-link");
  const authModeTabs = document.getElementById("auth-mode-tabs");
  const emailGroup = document.getElementById("email-group");
  const passwordGroup = document.getElementById("password-group");
  const passwordLabel = document.getElementById("password-label");
  const confirmPasswordGroup = document.getElementById("confirm-password-group");
  const confirmPasswordInput = document.getElementById("password-confirm");
  const termsConsentGroup = document.getElementById("terms-consent-group");
  const termsConsentInput = document.getElementById("terms-consent");
  const socialLoginWrap = document.getElementById("social-login-wrap");
  const googleLoginBtn = document.getElementById("google-login-btn");
  const telegramLoginWidget = document.getElementById("telegram-login-widget");
  const telegramLoginHint = document.getElementById("telegram-login-hint");
  const telegramLoginUnavailable = document.getElementById("telegram-login-unavailable");
  const resendVerificationBtn = document.getElementById("resend-verification-btn");
  const authNotice = document.getElementById("auth-notice");
  const authNoticeText = document.getElementById("auth-notice-text");
  const authNoticeDismiss = document.getElementById("auth-notice-dismiss");

  if (!form || !submitBtn) {
    return;
  }

  const dashboardUrl =
    window.location.protocol === "file:"
      ? "./lk/dashboard.html"
      : "/frontend/lk/dashboard.html";
  const profileUrl =
    window.location.protocol === "file:"
      ? "./lk/profile.html"
      : "/frontend/lk/profile.html";

  function resolvePostLoginUrl(data) {
    const target = data && data.redirect_to ? String(data.redirect_to).trim() : "";
    if (!target) {
      return dashboardUrl;
    }
    if (target.startsWith("http://") || target.startsWith("https://")) {
      return target;
    }
    if (window.location.protocol === "file:" && target.startsWith("/frontend/lk/")) {
      return "." + target.replace("/frontend/lk", "/lk");
    }
    return target;
  }

  const apiBases = (function resolveApiBases() {
    if (window.API_BASE_URL) {
      return [String(window.API_BASE_URL).replace(/\/+$/, "")];
    }
    if (window.location.protocol === "file:") {
      return ["http://localhost:5000/api"];
    }
    const localHosts = ["localhost", "127.0.0.1", "0.0.0.0"];
    const isLocalHost = localHosts.includes(window.location.hostname);
    if (isLocalHost && window.location.port && window.location.port !== "5000") {
      return [
        "/api",
        window.location.protocol + "//" + window.location.hostname + ":5000/api",
      ];
    }
    return ["/api"];
  })();

  let mode = "login";
  let resetToken = "";

  try {
    const params = new URLSearchParams(window.location.search);
    const urlToken = (params.get("token") || "").trim();
    if (urlToken && params.get("verified") !== "1" && !params.get("verify_error")) {
      mode = "reset";
      resetToken = urlToken;
    } else {
      const inv = (params.get("invite") || "").trim();
      if (inv) {
        sessionStorage.setItem("manager_invite_token", inv);
        mode = "register";
      }
    }
  } catch (_e) {
    /* ignore */
  }

  function getApiErrorMessage(data) {
    if (!data || typeof data !== "object") return t("login.requestError");
    const loc = window.LoginI18n ? window.LoginI18n.getLocale() : "ru";
    if (loc === "en") {
      return data.message_en || data.message_ru || data.error || t("login.requestError");
    }
    return data.message_ru || data.message_en || data.error || t("login.requestError");
  }

  function renderTabs() {
    const isLogin = mode === "login";
    const isRegister = mode === "register";
    const isForgot = mode === "forgot";
    const isReset = mode === "reset";
    const isAuthTab = isLogin || isRegister;

    if (authModeTabs) {
      authModeTabs.classList.toggle("hidden", !isAuthTab);
    }
    if (backToLoginLink) {
      backToLoginLink.classList.toggle("hidden", isAuthTab);
    }
    if (socialLoginWrap) {
      socialLoginWrap.classList.toggle("hidden", !isAuthTab);
    }
    if (emailGroup) {
      emailGroup.classList.toggle("hidden", isReset);
    }
    if (passwordGroup) {
      passwordGroup.classList.toggle("hidden", isForgot);
    }
    if (emailInput) {
      emailInput.required = !isReset;
    }
    if (passwordInput) {
      passwordInput.required = !isForgot;
    }
    if (termsConsentGroup) {
      termsConsentGroup.classList.toggle("hidden", !isRegister);
    }
    if (termsConsentInput) {
      termsConsentInput.required = isRegister;
      if (!isRegister) {
        termsConsentInput.checked = false;
      }
    }

    if (isLogin) {
      if (loginTab) {
        loginTab.className =
          "flex-1 py-2.5 text-sm font-semibold rounded-md bg-[rgba(255,255,255,0.1)] text-white shadow-sm transition-all";
      }
      if (registerTab) {
        registerTab.className =
          "flex-1 py-2.5 text-sm font-medium rounded-md text-secondary-fixed-dim hover:text-white transition-all";
      }
      submitBtn.textContent = t("login.submitLogin");
      if (confirmPasswordGroup) {
        confirmPasswordGroup.classList.add("hidden");
      }
      if (forgotPasswordLink) {
        forgotPasswordLink.classList.remove("hidden");
      }
      if (confirmPasswordInput) {
        confirmPasswordInput.required = false;
        confirmPasswordInput.value = "";
      }
      if (passwordLabel) {
        passwordLabel.textContent = t("login.password");
      }
      passwordInput.type = "password";
      passwordInput.placeholder = "••••••••";
    } else if (isRegister) {
      if (registerTab) {
        registerTab.className =
          "flex-1 py-2.5 text-sm font-semibold rounded-md bg-[rgba(255,255,255,0.1)] text-white shadow-sm transition-all";
      }
      if (loginTab) {
        loginTab.className =
          "flex-1 py-2.5 text-sm font-medium rounded-md text-secondary-fixed-dim hover:text-white transition-all";
      }
      submitBtn.textContent = t("login.submitRegister");
      if (confirmPasswordGroup) {
        confirmPasswordGroup.classList.remove("hidden");
      }
      if (forgotPasswordLink) {
        forgotPasswordLink.classList.add("hidden");
      }
      if (confirmPasswordInput) {
        confirmPasswordInput.required = true;
      }
      if (passwordLabel) {
        passwordLabel.textContent = t("login.password");
      }
      passwordInput.type = "password";
      passwordInput.placeholder = "••••••••";
    } else if (isForgot) {
      submitBtn.textContent = t("login.submitForgot");
      if (confirmPasswordGroup) {
        confirmPasswordGroup.classList.add("hidden");
      }
      if (forgotPasswordLink) {
        forgotPasswordLink.classList.add("hidden");
      }
      if (confirmPasswordInput) {
        confirmPasswordInput.required = false;
        confirmPasswordInput.value = "";
      }
    } else if (isReset) {
      submitBtn.textContent = t("login.submitReset");
      if (confirmPasswordGroup) {
        confirmPasswordGroup.classList.remove("hidden");
      }
      if (forgotPasswordLink) {
        forgotPasswordLink.classList.add("hidden");
      }
      if (confirmPasswordInput) {
        confirmPasswordInput.required = true;
      }
      if (passwordLabel) {
        passwordLabel.textContent = t("login.newPassword");
      }
      passwordInput.type = "password";
      passwordInput.placeholder = t("login.newPasswordPlaceholder");
    }

    errorBox.textContent = "";
    successBox.textContent = "";
    setResendVerificationVisible(false);
  }

  function showAuthNotice(message, variant) {
    if (!authNotice || !authNoticeText) {
      successBox.textContent = message;
      return;
    }
    authNoticeText.textContent = message;
    authNotice.classList.remove("hidden", "auth-notice--info", "auth-notice--success", "auth-notice--error");
    authNotice.classList.add(variant === "success" ? "auth-notice--success" : variant === "error" ? "auth-notice--error" : "auth-notice--info");
    authNotice.classList.remove("hidden");
    successBox.textContent = "";
    errorBox.textContent = "";
  }

  function hideAuthNotice() {
    if (!authNotice) {
      return;
    }
    authNotice.classList.add("hidden");
    if (authNoticeText) {
      authNoticeText.textContent = "";
    }
  }

  function setResendVerificationVisible(visible, email) {
    if (!resendVerificationBtn) {
      return;
    }
    if (visible) {
      resendVerificationBtn.classList.remove("hidden");
      resendVerificationBtn.dataset.email = email || "";
    } else {
      resendVerificationBtn.classList.add("hidden");
      resendVerificationBtn.dataset.email = "";
    }
  }

  async function resendVerificationEmail(targetEmail) {
    const email = String(targetEmail || emailInput.value || "").trim();
    if (!email) {
      return;
    }
    errorBox.textContent = "";
    successBox.textContent = "";
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + "/resend-verification", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ email }),
        });
        const data = await response.json().catch(function () {
          return {};
        });
        if (response.ok && data.success) {
          const sent = data.email_delivery && data.email_delivery.sent;
          successBox.textContent = sent
            ? t("login.resendVerificationSent")
            : t("login.resendVerificationFailed");
          setResendVerificationVisible(false);
          return;
        }
      } catch (_error) {
        /* try next base */
      }
    }
    errorBox.textContent = t("login.resendVerificationFailed");
  }

  function applyQueryMessages() {
    let params;
    try {
      params = new URLSearchParams(window.location.search);
    } catch (_e) {
      return;
    }
    const urlToken = (params.get("token") || "").trim();
    if (urlToken && params.get("verified") !== "1" && !params.get("verify_error")) {
      mode = "reset";
      resetToken = urlToken;
      renderTabs();
      return;
    }

    if (params.get("verified") === "1") {
      showAuthNotice(t("login.emailVerifiedSuccess"), "success");
      mode = "login";
      renderTabs();
    } else if (params.get("verify_error") === "expired") {
      showAuthNotice(t("login.verifyErrorExpired"), "error");
      setResendVerificationVisible(true, emailInput.value.trim());
      mode = "login";
      renderTabs();
    } else if (params.get("verify_error") === "invalid") {
      showAuthNotice(t("login.verifyErrorInvalid"), "error");
      mode = "login";
      renderTabs();
    } else if (params.get("account_deleted") === "1") {
      showAuthNotice(t("login.accountDeletedSuccess"), "info");
      mode = "login";
      renderTabs();
    }
    if (params.has("verified") || params.has("verify_error") || params.has("account_deleted")) {
      try {
        const clean = new URL(window.location.href);
        clean.searchParams.delete("verified");
        clean.searchParams.delete("verify_error");
        clean.searchParams.delete("account_deleted");
        clean.searchParams.delete("token");
        window.history.replaceState({}, "", clean.pathname + clean.search + clean.hash);
      } catch (_e) {
        /* ignore */
      }
    }
  }

  if (loginTab) {
    loginTab.addEventListener("click", function () {
      mode = "login";
      hideAuthNotice();
      renderTabs();
    });
  }

  if (registerTab) {
    registerTab.addEventListener("click", function () {
      mode = "register";
      hideAuthNotice();
      renderTabs();
    });
  }

  if (forgotPasswordLink) {
    forgotPasswordLink.addEventListener("click", function (event) {
      event.preventDefault();
      mode = "forgot";
      hideAuthNotice();
      renderTabs();
    });
  }

  if (backToLoginLink) {
    backToLoginLink.addEventListener("click", function () {
      mode = "login";
      resetToken = "";
      hideAuthNotice();
      renderTabs();
      try {
        const clean = new URL(window.location.href);
        clean.searchParams.delete("token");
        window.history.replaceState({}, "", clean.pathname + clean.search + clean.hash);
      } catch (_e) {
        /* ignore */
      }
    });
  }

  if (passwordToggleBtn && passwordToggleIcon) {
    passwordToggleBtn.addEventListener("click", function () {
      const isHidden = passwordInput.type === "password";
      passwordInput.type = isHidden ? "text" : "password";
      passwordToggleIcon.textContent = isHidden ? "visibility" : "visibility_off";
      passwordToggleBtn.setAttribute(
        "aria-label",
        t(isHidden ? "login.togglePasswordHide" : "login.togglePasswordShow")
      );
    });
  }

  async function postAuthEndpoint(path, body) {
    let response = null;
    let data = null;
    let requestError = null;

    for (const baseUrl of apiBases) {
      try {
        response = await fetch(baseUrl + path, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(body || {}),
        });
        const responseText = await response.text();
        data = responseText ? JSON.parse(responseText) : {};
        requestError = null;
        break;
      } catch (error) {
        requestError = error;
      }
    }

    if (requestError) {
      throw new Error(t("login.apiUnreachable"));
    }
    return { response, data };
  }

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    errorBox.textContent = "";
    successBox.textContent = "";

    const email = String(emailInput.value || "").trim();
    const password = String(passwordInput.value || "");
    const confirmPassword = String(confirmPasswordInput.value || "");

    try {
      if (mode === "forgot") {
        const { response, data } = await postAuthEndpoint("/forgot-password", { email });
        if (!response.ok || !data.success) {
          throw new Error(getApiErrorMessage(data));
        }
        showAuthNotice(t("login.forgotPasswordSent"), "info");
        mode = "login";
        renderTabs();
        return;
      }

      if (mode === "reset") {
        const token =
          resetToken ||
          (function () {
            try {
              return (new URLSearchParams(window.location.search).get("token") || "").trim();
            } catch (_e) {
              return "";
            }
          })();
        if (!token) {
          throw new Error(t("login.resetInvalidToken"));
        }
        if (!password || password !== confirmPassword) {
          throw new Error(
            password !== confirmPassword ? t("login.passwordMismatch") : t("login.resetPasswordRequired")
          );
        }
        const { response, data } = await postAuthEndpoint("/reset-password", {
          token,
          password,
        });
        if (!response.ok || !data.success) {
          throw new Error(getApiErrorMessage(data));
        }
        showAuthNotice(t("login.resetPasswordSuccess"), "success");
        resetToken = "";
        passwordInput.value = "";
        confirmPasswordInput.value = "";
        mode = "login";
        renderTabs();
        try {
          const clean = new URL(window.location.href);
          clean.searchParams.delete("token");
          window.history.replaceState({}, "", clean.pathname + clean.search + clean.hash);
        } catch (_e) {
          /* ignore */
        }
        return;
      }

      const endpointPath = mode === "login" ? "/login" : "/register";

      if (mode === "register" && password !== confirmPassword) {
        throw new Error(t("login.passwordMismatch"));
      }
      if (mode === "register" && termsConsentInput && !termsConsentInput.checked) {
        throw new Error(t("login.termsNotAccepted"));
      }

      let response = null;
      let data = null;
      let requestError = null;

      for (const baseUrl of apiBases) {
        const endpoint = baseUrl + endpointPath;
        try {
          const authBody =
            mode === "register"
              ? (function () {
                  const o = { email, password, terms_accepted: true };
                  const token = (
                    sessionStorage.getItem("manager_invite_token") ||
                    new URLSearchParams(window.location.search).get("invite") ||
                    ""
                  ).trim();
                  if (token) {
                    o.manager_invite_token = token;
                  }
                  return o;
                })()
              : { email, password };
          response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "include",
            body: JSON.stringify(authBody),
          });
          const responseText = await response.text();
          data = responseText ? JSON.parse(responseText) : {};
          requestError = null;
          break;
        } catch (error) {
          requestError = error;
        }
      }

      if (requestError) {
        throw new Error(t("login.apiUnreachable"));
      }

      if (!response.ok || !data.success) {
        if (data && data.error_code === "EMAIL_NOT_VERIFIED") {
          setResendVerificationVisible(true, email);
        } else {
          setResendVerificationVisible(false);
        }
        throw new Error(getApiErrorMessage(data));
      }

      setResendVerificationVisible(false);

      if (mode === "register") {
        const cid =
          data.display_id != null && String(data.display_id).trim()
            ? String(data.display_id).trim()
            : data.user_id != null
              ? String(data.user_id)
              : "";
        const emailSent = data.email_delivery && data.email_delivery.sent;
        if (data.verification_required && emailSent) {
          showAuthNotice(
            cid ? t("login.registerCheckEmailWithId", { id: cid }) : t("login.registerCheckEmail"),
            "info"
          );
        } else if (data.verification_required) {
          showAuthNotice(t("login.registerEmailFailed"), "error");
          setResendVerificationVisible(true, email);
        } else {
          successBox.textContent = cid
            ? t("login.registerSuccessWithId", { id: cid })
            : t("login.registerSuccess");
        }
        try {
          sessionStorage.removeItem("manager_invite_token");
        } catch (_e) {
          /* ignore */
        }
        mode = "login";
        renderTabs();
        passwordInput.value = "";
        confirmPasswordInput.value = "";
        if (termsConsentInput) {
          termsConsentInput.checked = false;
        }
        return;
      }

      localStorage.removeItem("token");
      window.location.href = resolvePostLoginUrl(data);
    } catch (error) {
      errorBox.textContent = error.message || t("login.genericError");
    }
  });

  async function postTelegramLogin(user) {
    let response = null;
    let data = null;
    let requestError = null;
    const inviteToken = (function () {
      try {
        return (
          sessionStorage.getItem("manager_invite_token") ||
          new URLSearchParams(window.location.search).get("invite") ||
          ""
        ).trim();
      } catch (_e) {
        return "";
      }
    })();

    const body = Object.assign({}, user || {});
    if (inviteToken) {
      body.manager_invite_token = inviteToken;
    }

    for (const baseUrl of apiBases) {
      try {
        response = await fetch(baseUrl + "/login/telegram", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify(body),
        });
        const responseText = await response.text();
        data = responseText ? JSON.parse(responseText) : {};
        requestError = null;
        break;
      } catch (error) {
        requestError = error;
      }
    }

    if (requestError) {
      throw new Error(t("login.apiUnreachable"));
    }
    if (!response.ok || !data.success) {
      throw new Error(getApiErrorMessage(data));
    }
    return data;
  }

  window.onTelegramAuth = async function (user) {
    errorBox.textContent = "";
    successBox.textContent = "";
    try {
      const data = await postTelegramLogin(user);
      try {
        sessionStorage.removeItem("manager_invite_token");
      } catch (_e) {
        /* ignore */
      }
      localStorage.removeItem("token");
      window.location.href = resolvePostLoginUrl(data);
    } catch (error) {
      errorBox.textContent = error.message || t("login.genericError");
    }
  };

  const TELEGRAM_BOT_FALLBACK = "spainza_bot";
  let telegramLoginPollTimer = 0;

  function renderTelegramAppLoginButton(botUsername) {
    if (!telegramLoginWidget) {
      return;
    }
    telegramLoginWidget.innerHTML =
      '<button type="button" class="social-btn telegram-app-login-btn flex w-full justify-center items-center gap-2 py-2.5 px-4 rounded-lg" id="telegram-app-login-btn">' +
      '<svg class="h-5 w-5 shrink-0" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><path d="M9.78 15.53 9.4 19.3c.55 0 .79-.24 1.08-.53l2.59-2.49 5.37 3.94c.99.55 1.69.26 1.95-.92l3.53-16.58h.01c.31-1.45-.52-2.02-1.47-1.67L1.17 9.78c-1.43.56-1.41 1.36-.26 1.72l5.55 1.73L19.61 6.3c.66-.43 1.27-.2.77.25"/></svg>' +
      '<span class="text-sm font-medium text-white">' +
      t("login.telegram") +
      "</span></button>";
    if (telegramLoginHint) {
      telegramLoginHint.classList.remove("hidden");
    }
    if (telegramLoginUnavailable) {
      telegramLoginUnavailable.classList.add("hidden");
    }
    document.getElementById("telegram-app-login-btn")?.addEventListener("click", function () {
      startTelegramAppLogin(botUsername);
    });
  }

  function stopTelegramLoginPolling() {
    if (telegramLoginPollTimer) {
      window.clearInterval(telegramLoginPollTimer);
      telegramLoginPollTimer = 0;
    }
  }

  function openTelegramApp(url, tgUrl) {
    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent || "");
    const target = isMobile && tgUrl ? tgUrl : url || tgUrl;
    if (!target) {
      return;
    }
    window.location.href = target;
  }

  async function pollTelegramAppLogin(pollToken) {
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(
          baseUrl + "/auth/telegram/app-login/status?token=" + encodeURIComponent(pollToken),
          { credentials: "include" }
        );
        if (!response.ok) {
          continue;
        }
        const data = await response.json();
        if (data && data.success && data.completed) {
          stopTelegramLoginPolling();
          try {
            sessionStorage.removeItem("manager_invite_token");
          } catch (_e) {
            /* ignore */
          }
          localStorage.removeItem("token");
          window.location.href = resolvePostLoginUrl(data);
          return true;
        }
        return false;
      } catch (_error) {
        /* try next base */
      }
    }
    return false;
  }

  async function startTelegramAppLogin(botUsername) {
    errorBox.textContent = "";
    successBox.textContent = "";
    stopTelegramLoginPolling();

    let payload = null;
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + "/auth/telegram/app-login", {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
        });
        if (!response.ok) {
          continue;
        }
        payload = await response.json();
        break;
      } catch (_error) {
        /* try next base */
      }
    }

    if (!payload || !payload.success || !payload.poll_token) {
      errorBox.textContent = t("login.telegramUnavailable");
      return;
    }

    successBox.textContent = t("login.telegramPending");
    openTelegramApp(payload.telegram_url, payload.tg_url);

    telegramLoginPollTimer = window.setInterval(function () {
      pollTelegramAppLogin(payload.poll_token);
    }, 2000);
    pollTelegramAppLogin(payload.poll_token);
  }

  async function initTelegramLoginWidget() {
    if (!telegramLoginWidget) {
      return;
    }

    telegramLoginWidget.innerHTML =
      '<p class="text-xs text-secondary-fixed-dim text-center">' + t("login.telegramLoading") + "</p>";

    let config = null;
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + "/auth/telegram/widget", {
          credentials: "include",
        });
        if (!response.ok) {
          continue;
        }
        config = await response.json();
        break;
      } catch (_error) {
        /* try next base */
      }
    }

    const botUsername =
      config && config.success && config.bot_username
        ? config.bot_username
        : TELEGRAM_BOT_FALLBACK;

    if (config && config.success && config.enabled) {
      renderTelegramAppLoginButton(botUsername);
      return;
    }

    telegramLoginWidget.innerHTML = "";
    if (telegramLoginUnavailable) {
      telegramLoginUnavailable.classList.remove("hidden");
    }
    if (telegramLoginHint) {
      telegramLoginHint.classList.add("hidden");
    }
  }

  if (resendVerificationBtn) {
    resendVerificationBtn.addEventListener("click", function () {
      resendVerificationEmail(resendVerificationBtn.dataset.email || emailInput.value);
    });
  }

  if (authNoticeDismiss) {
    authNoticeDismiss.addEventListener("click", function () {
      hideAuthNotice();
    });
  }

  if (googleLoginBtn) {
    googleLoginBtn.addEventListener("click", function () {
      errorBox.textContent = "";
      successBox.textContent = "";
      successBox.textContent = t("login.googleSoon");
    });
  }

  window.addEventListener("login-locale-change", function () {
    if (window.LoginI18n) {
      window.LoginI18n.applyDocument();
      window.LoginI18n.paintLocaleButtons();
    }
    renderTabs();
  });

  if (window.LoginI18n) {
    window.LoginI18n.applyDocument();
    window.LoginI18n.initLangSwitcher();
  }
  renderTabs();
  applyQueryMessages();
  initTelegramLoginWidget();
})();
