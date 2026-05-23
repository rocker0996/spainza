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
  const confirmPasswordGroup = document.getElementById("confirm-password-group");
  const confirmPasswordInput = document.getElementById("password-confirm");

  if (!form || !submitBtn) {
    return;
  }

  const dashboardUrl =
    window.location.protocol === "file:"
      ? "./lk/dashboard.html"
      : "/frontend/lk/dashboard.html";

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

  try {
    const params = new URLSearchParams(window.location.search);
    const inv = (params.get("invite") || "").trim();
    if (inv) {
      sessionStorage.setItem("manager_invite_token", inv);
      mode = "register";
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
    if (mode === "login") {
      loginTab.className =
        "flex-1 py-2.5 text-sm font-semibold rounded-md bg-[rgba(255,255,255,0.1)] text-white shadow-sm transition-all";
      registerTab.className =
        "flex-1 py-2.5 text-sm font-medium rounded-md text-secondary-fixed-dim hover:text-white transition-all";
      submitBtn.textContent = t("login.submitLogin");
      confirmPasswordGroup.classList.add("hidden");
      forgotPasswordLink.classList.remove("hidden");
      confirmPasswordInput.required = false;
      confirmPasswordInput.value = "";
    } else {
      registerTab.className =
        "flex-1 py-2.5 text-sm font-semibold rounded-md bg-[rgba(255,255,255,0.1)] text-white shadow-sm transition-all";
      loginTab.className =
        "flex-1 py-2.5 text-sm font-medium rounded-md text-secondary-fixed-dim hover:text-white transition-all";
      submitBtn.textContent = t("login.submitRegister");
      confirmPasswordGroup.classList.remove("hidden");
      forgotPasswordLink.classList.add("hidden");
      confirmPasswordInput.required = true;
    }
    errorBox.textContent = "";
    successBox.textContent = "";
  }

  loginTab.addEventListener("click", function () {
    mode = "login";
    renderTabs();
  });

  registerTab.addEventListener("click", function () {
    mode = "register";
    renderTabs();
  });

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

  form.addEventListener("submit", async function (event) {
    event.preventDefault();
    errorBox.textContent = "";
    successBox.textContent = "";

    const email = String(emailInput.value || "").trim();
    const password = String(passwordInput.value || "");
    const confirmPassword = String(confirmPasswordInput.value || "");
    const endpointPath = mode === "login" ? "/login" : "/register";

    try {
      if (mode === "register" && password !== confirmPassword) {
        throw new Error(t("login.passwordMismatch"));
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
                  const o = { email, password };
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
        throw new Error(getApiErrorMessage(data));
      }

      if (mode === "register") {
        const cid =
          data.display_id != null && String(data.display_id).trim()
            ? String(data.display_id).trim()
            : data.user_id != null
              ? String(data.user_id)
              : "";
        successBox.textContent = cid
          ? t("login.registerSuccessWithId", { id: cid })
          : t("login.registerSuccess");
        try {
          sessionStorage.removeItem("manager_invite_token");
        } catch (_e) {
          /* ignore */
        }
        mode = "login";
        renderTabs();
        passwordInput.value = "";
        confirmPasswordInput.value = "";
        return;
      }

      localStorage.removeItem("token");
      window.location.href = dashboardUrl;
    } catch (error) {
      errorBox.textContent = error.message || t("login.genericError");
    }
  });

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
})();
