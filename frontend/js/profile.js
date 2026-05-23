// Profile settings page interactions.
(function () {

  const DEFAULT_USER_AVATAR = "../img/Avatar.jpg";

  function resolveApiBases() {
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
  }

  const apiBases = resolveApiBases();

  function t(key, params) {
    return window.LkI18n ? window.LkI18n.t(key, params) : key;
  }
  /** Тот же ID, что в chat.js (чат поддержки). */
  const SUPPORT_USER_ID = 11;
  /** Маркер должен совпадать с chat.js для оформления в переписке. */
  const COMPLAINT_MESSAGE_PREFIX = "[[SPAINZA_MANAGER_COMPLAINT]]\n";

  let profileManagerIdAnimTimer = 0;

  const state = {
    avatar: "",
    locale: "ru",
    /** Сохраняется с сервера; PATCH отправляет то же значение (поле не редактируется в UI). */
    main_goal: "",
    currentUserId: null,
    /** Публичный код (две буквы + четыре цифры), для передачи менеджеру. */
    clientDisplayId: null,
    /** Публичный номер аккаунта поддержки (из GET /user). */
    supportDisplayId: null,
    assignedManager: null,
    notifications: {
      email: true,
      sms: false,
      whatsapp: true,
    },
  };

  const byId = {
    name: document.getElementById("profile-name"),
    nameDesktop: document.getElementById("profile-name-desktop"),
    email: document.getElementById("profile-email"),
    phone: document.getElementById("profile-phone"),
    accessRole: document.getElementById("profile-access-role"),
    accessRoleMobile: document.getElementById("profile-access-role-mobile"),
    accessLevel: document.getElementById("profile-access-level"),
    avatarPreview: document.getElementById("profile-avatar-preview"),
    avatarFileInput: document.getElementById("avatar-file-input"),
    changeAvatar: document.getElementById("change-avatar-btn"),
    saveProfile: document.getElementById("save-profile-btn"),
    saveStatus: document.getElementById("profile-save-status"),
    newRequest: document.getElementById("new-request-btn"),
    currentPassword: document.getElementById("password-current"),
    newPassword: document.getElementById("password-new"),
    newPasswordConfirm: document.getElementById("password-new-confirm"),
    updatePassword: document.getElementById("update-password-btn"),
    passwordStatus: document.getElementById("password-status"),
    configure2fa: document.getElementById("configure-2fa-btn"),
    securityLog: document.getElementById("security-log-btn"),
    securityLogModal: document.getElementById("security-log-modal"),
    closeSecurityLogModal: document.getElementById("close-security-log-modal-btn"),
    securityLogList: document.getElementById("security-log-list"),
    deleteAccount: document.getElementById("delete-account-btn"),
    managerPlaceholder: document.getElementById("profile-manager-placeholder"),
    managerDetails: document.getElementById("profile-manager-details"),
    managerAvatar: document.getElementById("profile-manager-avatar"),
    managerName: document.getElementById("profile-manager-name"),
    managerRole: document.getElementById("profile-manager-role"),
    managerEmail: document.getElementById("profile-manager-email"),
    managerMessageBtn: document.getElementById("profile-manager-message-btn"),
    managerComplainBtn: document.getElementById("profile-manager-complain-btn"),
    complaintModal: document.getElementById("complaint-modal"),
    complaintModalClose: document.getElementById("complaint-modal-close-btn"),
    complaintModalCancel: document.getElementById("complaint-modal-cancel-btn"),
    complaintModalSubmit: document.getElementById("complaint-modal-submit-btn"),
    complaintTextInput: document.getElementById("complaint-text-input"),
    complaintModalStatus: document.getElementById("complaint-modal-status"),
  };

  const toggleButtons = Array.from(document.querySelectorAll("[data-toggle]"));
  const localeButtons = Array.from(document.querySelectorAll("[data-locale-btn]"));

  if (!byId.saveProfile || !byId.email || (!byId.name && !byId.nameDesktop)) {
    return;
  }

  function mirrorProfileName(fromInput) {
    const v = String(fromInput?.value ?? "");
    if (byId.name && fromInput !== byId.name) {
      byId.name.value = v;
    }
    if (byId.nameDesktop && fromInput !== byId.nameDesktop) {
      byId.nameDesktop.value = v;
    }
  }

  function profileNameValueForSave() {
    return String(byId.name?.value ?? byId.nameDesktop?.value ?? "").trim();
  }

  function unlockCurrentPasswordField() {
    const el = byId.currentPassword;
    if (!el || !el.hasAttribute("readonly")) {
      return;
    }
    el.removeAttribute("readonly");
  }

  byId.currentPassword?.addEventListener("pointerdown", unlockCurrentPasswordField, {
    capture: true,
  });
  byId.currentPassword?.addEventListener("focus", unlockCurrentPasswordField);

  const profileStatusState = {
    save: { key: null, isError: false, params: null },
    password: { key: null, isError: false, params: null },
  };

  function setStatus(node, text, isError) {
    if (!node) {
      return;
    }
    node.textContent = text || "";
    node.classList.remove("text-red-600", "text-green-600", "text-on-surface-variant");
    if (!text) {
      node.classList.add("text-on-surface-variant");
      return;
    }
    node.classList.add(isError ? "text-red-600" : "text-green-600");
  }

  function setProfileStatus(slot, key, isError, params) {
    const stateSlot = profileStatusState[slot];
    if (!stateSlot) {
      return;
    }
    if (!key) {
      stateSlot.key = null;
      stateSlot.isError = false;
      stateSlot.params = null;
      setStatus(slot === "password" ? byId.passwordStatus : byId.saveStatus, "", false);
      return;
    }
    stateSlot.key = key;
    stateSlot.isError = Boolean(isError);
    stateSlot.params = params || null;
    const node = slot === "password" ? byId.passwordStatus : byId.saveStatus;
    setStatus(node, t(key, stateSlot.params), stateSlot.isError);
  }

  function refreshProfileStatusMessages() {
    ["save", "password"].forEach((slot) => {
      const stateSlot = profileStatusState[slot];
      if (stateSlot && stateSlot.key) {
        setProfileStatus(slot, stateSlot.key, stateSlot.isError, stateSlot.params);
      }
    });
  }

  function passwordErrorKey(message) {
    const code = String(message || "").trim();
    if (code === "invalid current password") {
      return "profile.passwordWrongCurrent";
    }
    if (code === "new password is too weak") {
      return "profile.passwordWeak";
    }
    return "profile.passwordUpdateFailed";
  }

  function formatLogDate(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return t("profile.dateUnknown");
    }
    const localeTag = window.LkI18n ? window.LkI18n.dateLocaleTag() : "ru-RU";
    return date.toLocaleString(localeTag, {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function translateSecurityLogEntry(log) {
    if (!log) return log;
    if (window.LkI18n && window.LkI18n.translateSecurityLogEntry) {
      return window.LkI18n.translateSecurityLogEntry(log);
    }
    return log;
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#39;");
  }

  async function copyToClipboard(text) {
    const value = String(text ?? "");
    if (!value) {
      return false;
    }
    try {
      await navigator.clipboard.writeText(value);
      return true;
    } catch {
      try {
        const ta = document.createElement("textarea");
        ta.value = value;
        ta.setAttribute("readonly", "");
        ta.style.position = "fixed";
        ta.style.left = "-9999px";
        document.body.appendChild(ta);
        ta.select();
        const ok = document.execCommand("copy");
        document.body.removeChild(ta);
        return Boolean(ok);
      } catch {
        return false;
      }
    }
  }

  /** Статичный ID (не копируется) — прежний компактный бейдж */
  const USER_ID_BADGE_VISUAL =
    "inline-flex min-w-[2.25rem] items-center justify-center rounded-lg bg-primary-fixed/60 px-2.5 py-1 text-sm font-semibold font-headline text-primary-container tabular-nums tracking-tight ring-1 ring-primary-container/15 border-0 align-middle shrink-0";
  const USER_ID_BADGE_STATIC_CLASS = `${USER_ID_BADGE_VISUAL} opacity-70 cursor-default pointer-events-none`;

  function clearProfileIdSlotLock(wrapEl, btnEl) {
    if (btnEl) {
      btnEl.style.removeProperty("width");
      btnEl.classList.remove("dashboard-id-btn--active");
    }
    if (wrapEl) {
      wrapEl.style.removeProperty("width");
    }
  }

  function lockProfileIdSlotForAnim(wrapEl, btnEl) {
    if (!btnEl) {
      return;
    }
    const w = Math.ceil(btnEl.getBoundingClientRect().width);
    const px = `${Math.max(w, 72)}px`;
    btnEl.style.width = px;
    if (wrapEl) {
      wrapEl.style.width = px;
    }
  }

  function getManagerInitials(displayName, email) {
    const n = String(displayName || "").trim();
    if (n) {
      const parts = n.split(/\s+/).filter(Boolean);
      if (parts.length >= 2 && parts[0][0] && parts[1][0]) {
        return (parts[0][0] + parts[1][0]).toUpperCase();
      }
      return n.substring(0, 2).toUpperCase();
    }
    const e = String(email || "").trim();
    if (e.length >= 2) {
      return e.substring(0, 2).toUpperCase();
    }
    return "??";
  }

  function renderAssignedManager(manager) {
    const ph = byId.managerPlaceholder;
    const box = byId.managerDetails;
    if (!ph || !box) {
      return;
    }
    window.clearTimeout(profileManagerIdAnimTimer);
    profileManagerIdAnimTimer = 0;

    const m = manager && manager.id != null ? manager : null;
    state.assignedManager = m;
    if (!m) {
      const sessionId =
        state.clientDisplayId ||
        (state.currentUserId != null && !Number.isNaN(state.currentUserId)
          ? String(state.currentUserId)
          : "—");
      const copyable = sessionId !== "—";
      ph.replaceChildren();
      ph.appendChild(
        document.createTextNode(t("profile.managerNotAssigned"))
      );
      if (copyable) {
        const wrap = document.createElement("div");
        wrap.className = "dashboard-id-wrap";
        wrap.id = "profile-user-id-wrap";

        const idBtn = document.createElement("button");
        idBtn.type = "button";
        idBtn.className = "dashboard-id-btn";

        const checkContainer = document.createElement("span");
        checkContainer.className = "dashboard-id-btn__checkmark-container";
        checkContainer.setAttribute("aria-hidden", "true");
        checkContainer.innerHTML =
          '<svg class="dashboard-id-btn__check-svg" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" focusable="false"><path class="dashboard-id-btn__check-path" pathLength="1" d="M5.5 12.6 L10.35 17.45 19.25 7.15"/></svg>';

        const label = document.createElement("span");
        label.className = "dashboard-id-btn__label";
        label.textContent = sessionId;

        idBtn.appendChild(checkContainer);
        idBtn.appendChild(label);
        wrap.appendChild(idBtn);

        idBtn.setAttribute("aria-label", t("common.copyId", { id: sessionId }));
        idBtn.addEventListener("click", async () => {
          if (idBtn.classList.contains("dashboard-id-btn--active")) {
            return;
          }
          const copied = await copyToClipboard(sessionId);
          if (!copied) {
            return;
          }
          lockProfileIdSlotForAnim(wrap, idBtn);
          void idBtn.offsetWidth;
          idBtn.classList.add("dashboard-id-btn--active");
          window.clearTimeout(profileManagerIdAnimTimer);
          profileManagerIdAnimTimer = window.setTimeout(() => {
            clearProfileIdSlotLock(wrap, idBtn);
            profileManagerIdAnimTimer = 0;
          }, 1000);
        });

        ph.appendChild(wrap);
      } else {
        const idSpan = document.createElement("span");
        idSpan.className = USER_ID_BADGE_STATIC_CLASS;
        idSpan.textContent = sessionId;
        ph.appendChild(idSpan);
      }
      ph.classList.remove("hidden");
      box.classList.add("hidden");
      return;
    }

    ph.classList.add("hidden");
    box.classList.remove("hidden");

    const name = String(m.name || "").trim() || t("common.manager");
    const email = String(m.email || "").trim();
    const managerRoleKey = m.role && m.role.key ? String(m.role.key) : "";

    if (byId.managerName) {
      byId.managerName.textContent = name;
    }
    if (byId.managerRole) {
      byId.managerRole.textContent =
        managerRoleKey && window.LkI18n
          ? window.LkI18n.roleLabel(managerRoleKey)
          : t("profile.personalManagerRole");
    }
    if (byId.managerEmail) {
      byId.managerEmail.textContent = email || "";
    }

    const av = byId.managerAvatar;
    if (av) {
      const avatarUrl = String(m.avatar || "").trim();
      const safeUrl =
        avatarUrl &&
        (/^https?:\/\//i.test(avatarUrl) ||
          avatarUrl.startsWith("/") ||
          /^data:image\//i.test(avatarUrl));
      if (safeUrl) {
        av.textContent = "";
        const img = document.createElement("img");
        img.src = avatarUrl;
        img.alt = name;
        img.className = "w-full h-full object-cover";
        av.appendChild(img);
      } else {
        av.textContent = getManagerInitials(name, email);
      }
    }

    if (byId.managerMessageBtn) {
      const open =
        m.display_id != null && String(m.display_id).trim()
          ? String(m.display_id).trim().toUpperCase()
          : "";
      byId.managerMessageBtn.href = open
        ? `./messages.html?openUserId=${encodeURIComponent(open)}`
        : "./messages.html";
    }
  }

  function showComplaintModal() {
    if (!byId.complaintModal || !state.assignedManager) {
      return;
    }
    if (byId.complaintTextInput) {
      byId.complaintTextInput.value = "";
    }
    if (byId.complaintModalStatus) {
      byId.complaintModalStatus.textContent = "";
      byId.complaintModalStatus.classList.remove("text-red-600", "text-green-600");
      byId.complaintModalStatus.classList.add("text-on-surface-variant");
    }
    byId.complaintModal.classList.remove("hidden");
    byId.complaintModal.classList.add("flex");
    byId.complaintTextInput?.focus();
  }

  function hideComplaintModal() {
    if (!byId.complaintModal) {
      return;
    }
    byId.complaintModal.classList.add("hidden");
    byId.complaintModal.classList.remove("flex");
  }

  function buildComplaintMessageText(manager, complaintBody) {
    const when = new Date().toLocaleString("ru-RU", {
      day: "2-digit",
      month: "long",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    const roleKey = manager.role && manager.role.key != null ? String(manager.role.key) : "—";
    const roleRu = manager.role && manager.role.name_ru ? String(manager.role.name_ru) : "—";
    const mid = manager.id != null ? String(manager.id) : "—";
    const mname = String(manager.name || "").trim() || "—";
    const memail = String(manager.email || "").trim() || "—";
    const rid =
      state.clientDisplayId ||
      (state.currentUserId != null ? String(state.currentUserId) : "—");
    const rname = profileNameValueForSave() || "—";
    const remail = String(byId.email?.value || "").trim() || "—";
    const body = String(complaintBody || "").trim();

    return `${COMPLAINT_MESSAGE_PREFIX}[ЖАЛОБА НА ЗАКРЕПЛЁННОГО МЕНЕДЖЕРА]

Дата и время: ${when}

— Менеджер (закреплён к кейсу в ЛК) —
Внутренний ID: ${mid}
Имя в профиле: ${mname}
Email: ${memail}
Роль (ключ): ${roleKey}
Роль (отображение): ${roleRu}

— Клиент (отправитель жалобы) —
Внутренний ID: ${rid}
Имя в профиле (на момент отправки): ${rname}
Email (на момент отправки): ${remail}

— Текст жалобы —
${body}
`;
  }

  async function submitComplaintToSupport() {
    if (!state.assignedManager) {
      return;
    }
    const text = String(byId.complaintTextInput?.value || "").trim();
    if (text.length < 10) {
      if (byId.complaintModalStatus) {
        byId.complaintModalStatus.textContent = t("profile.complaintTooShort");
        byId.complaintModalStatus.classList.remove("text-on-surface-variant", "text-green-600");
        byId.complaintModalStatus.classList.add("text-red-600");
      }
      return;
    }

    const btn = byId.complaintModalSubmit;
    if (btn) {
      btn.disabled = true;
    }
    if (byId.complaintModalStatus) {
      byId.complaintModalStatus.textContent = t("profile.complaintSending");
      byId.complaintModalStatus.classList.remove("text-red-600", "text-green-600");
      byId.complaintModalStatus.classList.add("text-on-surface-variant");
    }

    try {
      let created;
      let openUserParam = "";
      if (state.supportDisplayId) {
        const sid = String(state.supportDisplayId).trim().toUpperCase();
        created = await apiRequest("/conversations/create", "POST", {
          display_id: sid,
          restore: true,
        });
        openUserParam = sid;
      } else {
        created = await apiRequest("/conversations/create", "POST", {
          user_id: SUPPORT_USER_ID,
          restore: true,
        });
      }
      if (!created || !created.conversation_id) {
        throw new Error(t("profile.supportChatFailed"));
      }
      const messageText = buildComplaintMessageText(state.assignedManager, text);
      await apiRequest(`/conversations/${created.conversation_id}/messages`, "POST", {
        message_text: messageText,
      });
      hideComplaintModal();
      window.location.href = openUserParam
        ? `./messages.html?openUserId=${encodeURIComponent(openUserParam)}`
        : "./messages.html";
    } catch (error) {
      if (byId.complaintModalStatus) {
        byId.complaintModalStatus.textContent =
          error?.message === "User not found"
            ? t("profile.supportUnavailable")
            : t("profile.complaintFailed");
        byId.complaintModalStatus.classList.remove("text-on-surface-variant", "text-green-600");
        byId.complaintModalStatus.classList.add("text-red-600");
      }
    } finally {
      if (btn) {
        btn.disabled = false;
      }
    }
  }

  async function apiRequest(path, method, body) {
    let requestError = null;
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + path, {
          method,
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
          },
          body: body ? JSON.stringify(body) : undefined,
        });
        let payload = {};
        try {
          payload = await response.json();
        } catch (error) {
          payload = {};
        }
        if (!response.ok) {
          if (response.status === 401) {
            localStorage.removeItem("token");
            window.location.href = "../login.html";
            return null;
          }
          requestError = new Error(payload.error || "request failed");
          continue;
        }
        return payload;
      } catch (error) {
        requestError = error;
      }
    }

    throw requestError || new Error("api unavailable");
  }

  function renderToggles() {
    toggleButtons.forEach((button) => {
      const key = button.getAttribute("data-toggle");
      const knob = button.querySelector(`[data-toggle-knob="${key}"]`);
      const isOn = Boolean(state.notifications[key]);
      button.classList.toggle("bg-white/20", !isOn);
      button.classList.toggle("bg-white/40", isOn);
      if (knob) {
        knob.classList.toggle("left-1", !isOn);
        knob.classList.toggle("right-1", isOn);
        knob.classList.toggle("bg-white/50", !isOn);
        knob.classList.toggle("bg-white", isOn);
      }
    });
  }

  function renderLocaleButtons() {
    const activeLocale = window.LkI18n ? window.LkI18n.getLocale() : state.locale;
    localeButtons.forEach((button) => {
      const locale = button.getAttribute("data-locale-btn");
      const isActive = locale === activeLocale;
      button.className = isActive
        ? "flex-1 py-2 rounded-lg text-xs font-bold bg-white shadow-sm text-primary"
        : "flex-1 py-2 rounded-lg text-xs font-bold text-slate-500 hover:text-primary transition-colors";
    });
  }

  function resolveUiLocale(payload) {
    const stored = localStorage.getItem("userLocale");
    if (stored === "en" || stored === "ru") {
      return stored;
    }
    if (window.LkI18n) {
      const fromUi = window.LkI18n.getLocale();
      if (fromUi === "en" || fromUi === "ru") {
        return fromUi;
      }
    }
    return payload && payload.locale === "en" ? "en" : "ru";
  }

  function applyProfilePayload(payload) {
    if (!payload) {
      return;
    }
    const uid = payload.id;
    state.currentUserId =
      typeof uid === "number" && !Number.isNaN(uid) ? uid : parseInt(String(uid), 10) || null;
    const did = String(payload.display_id || "").trim();
    state.clientDisplayId = did || null;
    state.supportDisplayId = payload.support_display_id
      ? String(payload.support_display_id).trim().toUpperCase()
      : null;

    const nextName = payload.name || "";
    if (byId.name) {
      byId.name.value = nextName;
    }
    if (byId.nameDesktop) {
      byId.nameDesktop.value = nextName;
    }
    byId.email.value = payload.email || "";
    byId.phone.value = payload.phone || "";
    state.main_goal = String(payload.main_goal || "").trim();

    const role = payload.role && typeof payload.role === "object" ? payload.role : null;
    const accountRoleLabel =
      role?.key && window.LkI18n
        ? window.LkI18n.roleLabel(role.key)
        : role?.name_ru || "—";
    if (byId.accessRole) {
      byId.accessRole.textContent = accountRoleLabel;
    }
    if (byId.accessRoleMobile) {
      byId.accessRoleMobile.textContent = accountRoleLabel;
    }
    if (byId.accessLevel) {
      const lvl = role?.level;
      const hasLevel = typeof lvl === "number" && !Number.isNaN(lvl);
      byId.accessLevel.textContent = hasLevel ? t("common.level", { n: lvl }) : "";
      byId.accessLevel.classList.toggle("hidden", !hasLevel);
    }

    state.avatar = String(payload.avatar || "").trim();
    state.locale = resolveUiLocale(payload);
    if (window.LkI18n && window.LkI18n.getLocale() !== state.locale) {
      window.LkI18n.setLocale(state.locale);
    }
    if (payload.notifications && typeof payload.notifications === "object") {
      state.notifications.email = Boolean(payload.notifications.email);
      state.notifications.sms = Boolean(payload.notifications.sms);
      state.notifications.whatsapp = Boolean(payload.notifications.whatsapp);
    }

    if (byId.avatarPreview) {
      byId.avatarPreview.src = state.avatar || DEFAULT_USER_AVATAR;
    }

    renderToggles();
    renderLocaleButtons();
    renderAssignedManager(payload.assigned_manager ?? null);
    window.syncProfileNameRequiredMarkers?.(nextName);
  }

  async function loadProfile() {
    try {
      const payload = await apiRequest("/user", "GET");
      if (!payload) {
        return;
      }
      applyProfilePayload(payload);
      window.persistUserProfileAndRefreshUi?.(payload);
    } catch (error) {
      const cachedRaw = localStorage.getItem("currentUserProfile");
      if (!cachedRaw) {
        renderAssignedManager(null);
        return;
      }
      try {
        applyProfilePayload(JSON.parse(cachedRaw));
      } catch (parseError) {
        renderAssignedManager(null);
      }
    }
  }

  async function saveProfile() {
    setProfileStatus("save", "profile.saving", false);
    const profilePayload = {
      name: profileNameValueForSave(),
      email: String(byId.email.value || "").trim(),
      phone: String(byId.phone.value || "").trim(),
      main_goal: String(state.main_goal || "").trim(),
      avatar: state.avatar,
      locale: window.LkI18n ? window.LkI18n.getLocale() : state.locale,
      notifications: {
        email: Boolean(state.notifications.email),
        sms: Boolean(state.notifications.sms),
        whatsapp: Boolean(state.notifications.whatsapp),
      },
    };

    try {
      const response = await apiRequest("/user", "PATCH", profilePayload);
      if (!response || !response.success) {
        throw new Error("save failed");
      }
      const savedLocale = window.LkI18n ? window.LkI18n.getLocale() : state.locale;
      state.locale = savedLocale === "en" ? "en" : "ru";
      let merged = { ...profilePayload, locale: state.locale };
      try {
        const prevRaw = localStorage.getItem("currentUserProfile");
        if (prevRaw) {
          const prev = JSON.parse(prevRaw);
          if (prev && typeof prev === "object") {
            merged = { ...prev, ...profilePayload, locale: state.locale };
          }
        }
      } catch {
        // оставляем merged только из полей формы
      }
      if (typeof window.persistUserProfileAndRefreshUi === "function") {
        window.persistUserProfileAndRefreshUi(merged);
      } else {
        try {
          localStorage.setItem("currentUserProfile", JSON.stringify(merged));
          localStorage.setItem("currentUserProfileSavedAt", String(Date.now()));
        } catch {
          // ignore
        }
      }
      setProfileStatus("save", "profile.saved", false);
      window.syncProfileNameRequiredMarkers?.(profileNameValueForSave());
    } catch (error) {
      setProfileStatus(
        "save",
        error?.message === "email already exists" ? "profile.emailTaken" : "profile.saveFailed",
        true
      );
    }
  }

  async function updatePassword() {
    const currentPassword = String(byId.currentPassword.value || "");
    const newPassword = String(byId.newPassword.value || "");
    const newPasswordConfirm = String(byId.newPasswordConfirm?.value || "");
    if (!currentPassword || !newPassword) {
      setProfileStatus("password", "profile.passwordEnterBoth", true);
      return;
    }
    if (byId.newPasswordConfirm && newPassword !== newPasswordConfirm) {
      setProfileStatus("password", "profile.passwordMismatch", true);
      return;
    }

    setProfileStatus("password", "profile.passwordUpdating", false);
    try {
      const payload = await apiRequest("/user/password", "PATCH", {
        current_password: currentPassword,
        new_password: newPassword,
      });
      if (!payload || !payload.success) {
        throw new Error("password update failed");
      }
      byId.currentPassword.value = "";
      byId.currentPassword.setAttribute("readonly", "");
      byId.newPassword.value = "";
      if (byId.newPasswordConfirm) {
        byId.newPasswordConfirm.value = "";
      }
      setProfileStatus("password", "profile.passwordUpdated", false);
    } catch (error) {
      setProfileStatus("password", passwordErrorKey(error?.message), true);
    }
  }

  function showSecurityLogModal() {
    if (!byId.securityLogModal) {
      return;
    }
    byId.securityLogModal.classList.remove("hidden");
    byId.securityLogModal.classList.add("flex");
  }

  function hideSecurityLogModal() {
    if (!byId.securityLogModal) {
      return;
    }
    byId.securityLogModal.classList.add("hidden");
    byId.securityLogModal.classList.remove("flex");
  }

  function renderSecurityLogs(logs) {
    if (!byId.securityLogList) {
      return;
    }
    if (!Array.isArray(logs) || !logs.length) {
      byId.securityLogList.innerHTML =
        `<p class="text-sm text-on-surface-variant">${t("profile.securityLogEmpty")}</p>`;
      return;
    }

    byId.securityLogList.innerHTML = logs
      .map((log) => {
        const entry = translateSecurityLogEntry(log);
        const details = entry.details ? escapeHtml(entry.details) : t("profile.securityNoDetails");
        const ipAddress = entry.ip_address
          ? t("profile.securityIp", { ip: escapeHtml(entry.ip_address) })
          : t("profile.securityIpUnknown");
        return `
          <article class="p-4 rounded-xl bg-slate-50 border border-slate-100">
            <div class="flex items-start justify-between gap-3">
              <h4 class="font-semibold text-on-surface">${escapeHtml(entry.event_title || t("profile.securityEventDefault"))}</h4>
              <span class="text-xs text-outline whitespace-nowrap">${formatLogDate(log.created_at)}</span>
            </div>
            <p class="text-sm text-on-surface-variant mt-2">${details}</p>
            <p class="text-xs text-outline mt-2">${ipAddress}</p>
          </article>
        `;
      })
      .join("");
  }

  async function openSecurityLogs() {
    showSecurityLogModal();
    if (byId.securityLogList) {
      byId.securityLogList.innerHTML =
        `<p class="text-sm text-on-surface-variant">${t("profile.securityLogLoading")}</p>`;
    }
    try {
      const payload = await apiRequest("/user/security-logs", "GET");
      if (!payload || !payload.success) {
        throw new Error("logs failed");
      }
      renderSecurityLogs(payload.logs || []);
    } catch (error) {
      if (byId.securityLogList) {
        byId.securityLogList.innerHTML =
          `<p class="text-sm text-red-600">${t("profile.securityLogFailed")}</p>`;
      }
    }
  }

  toggleButtons.forEach((button) => {
    button.addEventListener("click", () => {
      const key = button.getAttribute("data-toggle");
      if (!key) {
        return;
      }
      state.notifications[key] = !state.notifications[key];
      renderToggles();
    });
  });

  byId.changeAvatar?.addEventListener("click", () => {
    byId.avatarFileInput?.click();
  });

  byId.avatarFileInput?.addEventListener("change", () => {
    const file = byId.avatarFileInput.files?.[0];
    if (!file) {
      return;
    }
    if (!file.type.startsWith("image/")) {
      window.alert(t("profile.avatarImageOnly"));
      byId.avatarFileInput.value = "";
      return;
    }
    if (file.size > 3 * 1024 * 1024) {
      window.alert(t("profile.avatarMaxSize"));
      byId.avatarFileInput.value = "";
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      if (!result.startsWith("data:image/")) {
        window.alert(t("profile.avatarReadError"));
        return;
      }
      state.avatar = result;
      if (byId.avatarPreview) {
        byId.avatarPreview.src = state.avatar;
      }
      setProfileStatus("save", "profile.avatarSelected", false);
    };
    reader.onerror = () => {
      window.alert(t("profile.avatarFileError"));
    };
    reader.readAsDataURL(file);
  });

  byId.name?.addEventListener("input", (event) => {
    mirrorProfileName(event.target);
    window.syncProfileNameRequiredMarkers?.(profileNameValueForSave());
  });
  byId.nameDesktop?.addEventListener("input", (event) => {
    mirrorProfileName(event.target);
    window.syncProfileNameRequiredMarkers?.(profileNameValueForSave());
  });

  byId.saveProfile.addEventListener("click", saveProfile);
  byId.updatePassword?.addEventListener("click", updatePassword);
  byId.newPassword?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      updatePassword();
    }
  });
  byId.newPasswordConfirm?.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      updatePassword();
    }
  });
  byId.newRequest?.addEventListener("click", () => {
    window.location.href = "./status.html";
  });
  byId.configure2fa?.addEventListener("click", () => {
    window.alert(t("profile.subscriptionSoon"));
  });
  byId.securityLog?.addEventListener("click", openSecurityLogs);
  byId.closeSecurityLogModal?.addEventListener("click", hideSecurityLogModal);
  byId.securityLogModal?.addEventListener("click", (event) => {
    if (event.target === byId.securityLogModal) {
      hideSecurityLogModal();
    }
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") {
      hideComplaintModal();
      hideSecurityLogModal();
    }
  });

  byId.managerComplainBtn?.addEventListener("click", () => {
    if (!state.assignedManager) {
      return;
    }
    showComplaintModal();
  });
  byId.complaintModalClose?.addEventListener("click", hideComplaintModal);
  byId.complaintModalCancel?.addEventListener("click", hideComplaintModal);
  byId.complaintModalSubmit?.addEventListener("click", submitComplaintToSupport);
  byId.complaintModal?.addEventListener("click", (event) => {
    if (event.target === byId.complaintModal) {
      hideComplaintModal();
    }
  });
  byId.deleteAccount?.addEventListener("click", async () => {
    const confirmed = window.confirm(t("profile.deleteConfirm"));
    if (!confirmed) {
      return;
    }
    try {
      const payload = await apiRequest("/user", "DELETE");
      if (!payload || !payload.success) {
        throw new Error("delete failed");
      }
      localStorage.removeItem("token");
      localStorage.removeItem("currentUserProfile");
      localStorage.removeItem("currentUserProfileSavedAt");
      window.location.href = "../login.html";
    } catch (error) {
      window.alert(t("profile.deleteFailed"));
    }
  });

  renderToggles();
  renderLocaleButtons();
  loadProfile();

  window.addEventListener("lk-locale-change", () => {
    if (window.LkI18n) {
      state.locale = window.LkI18n.getLocale();
      window.LkI18n.applyDocument();
      renderLocaleButtons();
    }
    refreshProfileStatusMessages();
    renderAssignedManager(state.assignedManager);
    if (byId.securityLogModal && !byId.securityLogModal.classList.contains("hidden")) {
      openSecurityLogs();
    }
  });
})();
