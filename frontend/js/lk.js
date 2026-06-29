// Simple auth guard for /lk/* pages.
(function () {
  const loginUrl =
    window.location.protocol === "file:"
      ? "../login.html"
      : "/frontend/login.html";
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

  function clearLocalSession() {
    localStorage.removeItem("token");
    localStorage.removeItem("currentUserProfile");
    localStorage.removeItem("currentUserProfileSavedAt");
  }

  async function revokeServerSession() {
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + "/logout", {
          method: "POST",
          credentials: "include",
        });
        if (response.ok || response.status === 401) {
          return;
        }
      } catch (error) {
        // Try next API base.
      }
    }
  }

  const logoutButton = document.getElementById("logout-btn");
  if (logoutButton) {
    logoutButton.addEventListener("click", async (event) => {
      event.preventDefault();
      event.stopImmediatePropagation();
      await revokeServerSession();
      clearLocalSession();
      window.location.href = loginUrl;
    }, true);
  }

  /** См. style#lk-gate-nav-css в head страниц ЛК — скрытие [data-lk-gate] до класса lk-gate-visible. */
  const defaultAvatar = "../img/Avatar.jpg";

  function resolveDisplayName(name, email) {
    if (name && String(name).trim()) {
      return String(name).trim();
    }
    if (email && String(email).includes("@")) {
      return String(email).split("@")[0];
    }
    return "\u2014";
  }

  function formatCreatedAt(createdAt) {
    const localeTag = window.LkI18n?.getLocale() === "en" ? "en-US" : "ru-RU";
    const empty = window.LkI18n
      ? window.LkI18n.t("common.memberSinceEmpty")
      : "Member since —";
    if (!createdAt) {
      return empty;
    }
    const parsedDate = window.LkI18n?.parseInstant(createdAt) || new Date(createdAt);
    if (Number.isNaN(parsedDate.getTime())) {
      return empty;
    }
    const prefix = window.LkI18n
      ? window.LkI18n.t("common.memberSince")
      : "Member since";
    return `${prefix} ${parsedDate.toLocaleDateString(localeTag)}`;
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

  let dashboardUserIdCopyAnimTimer = 0;

  function clearDashboardIdSlotLock(btn) {
    const wrap = document.getElementById("user-id-wrap");
    if (btn && btn instanceof HTMLElement) {
      btn.style.removeProperty("width");
    }
    if (wrap) {
      wrap.style.removeProperty("width");
    }
  }

  /** Фиксирует ширину кнопки и слота: сжатие к кругу идёт от центра (обёртка + flex center). */
  function lockDashboardIdSlotForAnim(btn) {
    if (!btn || !(btn instanceof HTMLElement)) {
      return;
    }
    const wrap = document.getElementById("user-id-wrap");
    const w = Math.ceil(btn.getBoundingClientRect().width);
    const px = `${Math.max(w, 72)}px`;
    btn.style.width = px;
    if (wrap) {
      wrap.style.width = px;
    }
  }

  const NOT_FOUND_URL =
    window.LK_NOT_FOUND_URL ||
    (function resolveLkNotFoundUrl() {
      const path = window.location.pathname || "";
      if (path.includes("/lk/")) {
        return "./404.html";
      }
      return "/frontend/lk/404.html";
    })();

  function lkRedirectAccessDeniedImpl() {
    if ((window.location.pathname || "").includes("404.html")) {
      return;
    }
    window.location.replace(NOT_FOUND_URL);
  }

  if (typeof window.redirectLkAccessDenied !== "function") {
    window.redirectLkAccessDenied = lkRedirectAccessDeniedImpl;
  }
  if (!window.LK_NOT_FOUND_URL) {
    window.LK_NOT_FOUND_URL = NOT_FOUND_URL;
  }

  const redirectLkAccessDenied = window.redirectLkAccessDenied;

  function hasPermission(userData, permission) {
    const permissions = Array.isArray(userData.permissions) ? userData.permissions : [];
    return permissions.includes("full_access") || permissions.includes(permission);
  }

  function canAccessClientsPage(userData) {
    return (
      hasPermission(userData, "full_access") ||
      hasPermission(userData, "view_all_users") ||
      hasPermission(userData, "view_lower_users") ||
      hasPermission(userData, "view_assignable_users") ||
      hasPermission(userData, "view_assigned_clients")
    );
  }

  function canAccessDocumentsPage(userData) {
    const staff = isPortalStaffRole(userData);
    if (!staff) {
      return (
        hasPermission(userData, "upload_documents") ||
        hasPermission(userData, "download_documents") ||
        hasPermission(userData, "review_documents") ||
        hasPermission(userData, "approve_documents")
      );
    }
    let hasClientParam = false;
    try {
      const params = new URLSearchParams(window.location.search);
      hasClientParam = Boolean(
        (params.get("client") || "").trim() || (params.get("userId") || "").trim()
      );
    } catch {
      hasClientParam = false;
    }
    if (!hasClientParam) {
      return false;
    }
    return (
      hasPermission(userData, "view_assigned_clients") ||
      hasPermission(userData, "review_documents") ||
      hasPermission(userData, "approve_documents") ||
      hasPermission(userData, "full_access")
    );
  }

  function canAccessConfiguratorPage(userData) {
    return isPortalStaffRole(userData);
  }

  function canAccessAdminAuditPage(userData) {
    if (hasPermission(userData, "full_access")) {
      return true;
    }
    const roleKey = String(
      (userData && userData.role && (userData.role.key || userData.role.role_key)) || ""
    ).toLowerCase();
    return roleKey === "management";
  }

  function canAccessPageGate(userData, gate) {
    if (!gate || gate === "none") {
      return true;
    }
    switch (gate) {
      case "clients":
      case "case":
        return canAccessClientsPage(userData);
      case "documents":
        return canAccessDocumentsPage(userData);
      case "configurator":
        return canAccessConfiguratorPage(userData);
      case "admin-audit":
        return canAccessAdminAuditPage(userData);
      default:
        return true;
    }
  }

  function enforceLkPageGate(userData) {
    const gate = document.body && document.body.getAttribute("data-lk-page-gate");
    if (!gate || gate === "none") {
      return;
    }
    if (!canAccessPageGate(userData, gate)) {
      redirectLkAccessDenied();
    }
  }

  /** Персонал ЛК: уровень роли 1–4 (management … manager). */
  function isPortalStaffRole(userData) {
    const raw = userData && userData.role && userData.role.level;
    const level = parseFloat(String(raw ?? ""), 10);
    return !Number.isNaN(level) && level <= 4;
  }

  function applyRoleDataToUi(userData) {
    const roleNameNode = document.getElementById("user-role-name");
    const roleLevelNode = document.getElementById("user-role-level");
    const roleData = userData.role || {};
    const uiLocale = window.LkI18n?.getLocale() === "en" ? "en" : "ru";
    const roleKey = roleData.key || roleData.role_key || "";
    const roleName =
      (window.LkI18n && roleKey
        ? window.LkI18n.roleLabel(roleKey)
        : null) ||
      (uiLocale === "en" ? roleData.name_en : roleData.name_ru) ||
      roleData.name_ru ||
      roleData.name_en ||
      "\u2014";
    const caseStatus =
      (uiLocale === "en"
        ? userData.case_status_en || userData.application_status_en
        : userData.case_status_ru || userData.application_status_ru) ||
      userData.case_status ||
      userData.application_status ||
      "\u2014";

    if (roleNameNode) {
      roleNameNode.textContent = roleName;
    }
    if (roleLevelNode) {
      roleLevelNode.textContent = String(caseStatus).trim() || "\u2014";
    }
  }

  function setGatedVisibility(elements, allowed) {
    elements.forEach((el) => {
      el.classList.toggle("lk-gate-visible", allowed);
      if (allowed) {
        el.removeAttribute("hidden");
        el.classList.remove("hidden");
      } else {
        el.classList.remove("lk-gate-visible");
        el.setAttribute("hidden", "");
        el.classList.add("hidden");
      }
    });
  }

  function togglePageAccess(userData) {
    const staff = isPortalStaffRole(userData);

    const canAccessDocuments =
      !staff &&
      (hasPermission(userData, "upload_documents") ||
        hasPermission(userData, "download_documents") ||
        hasPermission(userData, "review_documents") ||
        hasPermission(userData, "approve_documents"));

    const canAccessMessages = true;

    const canCreateApplication = hasPermission(userData, "request_role_change");

    const canAccessClients = canAccessClientsPage(userData);

    const canAccessConfigurator = canAccessConfiguratorPage(userData);

    setGatedVisibility(document.querySelectorAll('[data-lk-gate="documents"]'), canAccessDocuments);

    setGatedVisibility(document.querySelectorAll('[data-lk-gate="configurator"]'), canAccessConfigurator);

    setGatedVisibility(document.querySelectorAll('[data-lk-gate="messages"]'), canAccessMessages);

    setGatedVisibility(document.querySelectorAll('[data-lk-gate="clients"]'), canAccessClients);

    setGatedVisibility(document.querySelectorAll('[data-lk-gate="new-request"]'), canCreateApplication);
  }

  function publishLkUser(userData) {
    if (!userData || userData.id == null) {
      return;
    }
    window.__lkCurrentUser = userData;
    try {
      window.dispatchEvent(new CustomEvent("lk-user-ready", { detail: userData }));
    } catch {
      // ignore
    }
  }

  function applyUserDataToUi(userData) {
    const displayName = resolveDisplayName(userData.name, userData.email);

    const titleName = document.getElementById("user-name-title");
    if (titleName) {
      titleName.textContent = displayName;
    }

    const cardName = document.getElementById("user-name-card");
    if (cardName) {
      cardName.textContent = displayName;
    }

    const email = document.getElementById("user-email");
    if (email) {
      email.textContent = userData.email || "\u2014";
    }

    const uid = userData.id;
    const idStr =
      (userData.display_id && String(userData.display_id).trim()) ||
      (uid != null && String(uid).trim() !== "" ? String(uid) : "—");

    const userIdMobileValue = document.getElementById("user-id-mobile-value");
    const userIdMobileCopy = document.getElementById("user-id-mobile-copy");
    if (userIdMobileValue) {
      userIdMobileValue.textContent = idStr;
    }
    if (userIdMobileCopy instanceof HTMLButtonElement) {
      userIdMobileCopy.disabled = idStr === "—";
      if (idStr === "—") {
        userIdMobileCopy.removeAttribute("aria-label");
        userIdMobileCopy.onclick = null;
      } else {
        userIdMobileCopy.setAttribute(
          "aria-label",
          window.LkI18n
            ? window.LkI18n.t("common.copyId", { id: idStr })
            : `Скопировать ID ${idStr}`
        );
        userIdMobileCopy.onclick = async () => {
          const copied = await copyToClipboard(idStr);
          if (!copied) return;
          const prev = userIdMobileValue ? userIdMobileValue.textContent : "";
          if (userIdMobileValue) {
            userIdMobileValue.textContent = window.LkI18n
              ? window.LkI18n.t("common.copied")
              : "copied";
          }
          window.setTimeout(() => {
            if (userIdMobileValue) userIdMobileValue.textContent = prev || idStr;
          }, 900);
        };
      }
    }

    const userIdValue = document.getElementById("user-id-value");
    const userIdValueLabel = document.getElementById("user-id-value-label");
    if (userIdValue) {
      window.clearTimeout(dashboardUserIdCopyAnimTimer);
      dashboardUserIdCopyAnimTimer = 0;
      userIdValue.classList.remove("dashboard-id-btn--active");
      if (userIdValueLabel) {
        userIdValueLabel.textContent = idStr;
      } else {
        userIdValue.textContent = idStr;
      }
      if (userIdValue instanceof HTMLButtonElement) {
        userIdValue.disabled = idStr === "—";
        if (idStr === "—") {
          userIdValue.removeAttribute("aria-label");
          userIdValue.onclick = null;
          clearDashboardIdSlotLock(userIdValue);
        } else {
          userIdValue.removeAttribute("title");
          userIdValue.setAttribute(
            "aria-label",
            window.LkI18n
              ? window.LkI18n.t("common.copyId", { id: idStr })
              : `Скопировать ID ${idStr}`
          );
          clearDashboardIdSlotLock(userIdValue);
          userIdValue.onclick = async () => {
            if (userIdValue.classList.contains("dashboard-id-btn--active")) {
              return;
            }
            const copied = await copyToClipboard(idStr);
            if (!copied) {
              return;
            }
            lockDashboardIdSlotForAnim(userIdValue);
            void userIdValue.offsetWidth;
            userIdValue.classList.add("dashboard-id-btn--active");
            window.clearTimeout(dashboardUserIdCopyAnimTimer);
            dashboardUserIdCopyAnimTimer = window.setTimeout(() => {
              userIdValue.classList.remove("dashboard-id-btn--active");
              clearDashboardIdSlotLock(userIdValue);
              dashboardUserIdCopyAnimTimer = 0;
            }, 1000);
          };
        }
      }
    }

    const createdAt = document.getElementById("user-created-at");
    if (createdAt) {
      createdAt.textContent = formatCreatedAt(userData.created_at);
    }
    const createdAtMobile = document.getElementById("user-created-at-mobile");
    if (createdAtMobile) {
      createdAtMobile.textContent = formatCreatedAt(userData.created_at);
    }

    const avatar = document.getElementById("user-avatar");
    if (avatar) {
      avatar.src = userData.avatar || defaultAvatar;
      avatar.alt = window.LkI18n
        ? window.LkI18n.t("common.avatarOf", { name: displayName })
        : displayName + " avatar";
    }

    applyRoleDataToUi(userData);
    togglePageAccess(userData);
    enforceLkPageGate(userData);
    syncProfileNameRequiredMarkers(userData.name);
    publishLkUser(userData);
  }

  /** Сохранить полный профиль в localStorage и обновить шапку/навигацию ЛК (вызывается из profile.js после GET/PATCH). */
  function persistUserProfileAndRefreshUi(payload) {
    if (!payload || typeof payload !== "object") {
      return;
    }
    try {
      localStorage.setItem("currentUserProfile", JSON.stringify(payload));
      localStorage.setItem("currentUserProfileSavedAt", String(Date.now()));
    } catch {
      return;
    }
    if (payload.locale === "en" || payload.locale === "ru") {
      const stored = localStorage.getItem("userLocale");
      const nextLocale =
        stored === "en" || stored === "ru" ? stored : payload.locale;
      if (window.LkI18n) {
        if (window.LkI18n.getLocale() !== nextLocale) {
          window.LkI18n.setLocale(nextLocale);
        } else {
          window.LkI18n.applyDocument();
        }
      } else {
        localStorage.setItem("userLocale", nextLocale);
      }
    }
    applyUserDataToUi(payload);
  }

  function initLocaleSwitcher() {
    const localeButtons = document.querySelectorAll("[data-locale-btn]");
    if (localeButtons.length === 0) {
      return;
    }

    function currentLocale() {
      return window.LkI18n ? window.LkI18n.getLocale() : localStorage.getItem("userLocale") || "ru";
    }

    function renderLocaleButtons() {
      const active = currentLocale();
      localeButtons.forEach((button) => {
        const locale = button.getAttribute("data-locale-btn");
        const isActive = locale === active;
        button.className = isActive
          ? "flex-1 py-2 rounded-lg text-xs font-bold bg-white shadow-sm text-primary"
          : "flex-1 py-2 rounded-lg text-xs font-bold text-slate-500 hover:text-primary transition-colors";
      });
    }

    localeButtons.forEach((button) => {
      button.addEventListener("click", () => {
        const selectedLocale = button.getAttribute("data-locale-btn");
        if (window.LkI18n) {
          window.LkI18n.setLocale(selectedLocale === "en" ? "en" : "ru");
        } else {
          localStorage.setItem("userLocale", selectedLocale === "en" ? "en" : "ru");
        }
        renderLocaleButtons();
        try {
          const cached = localStorage.getItem("currentUserProfile");
          if (cached) {
            applyUserDataToUi(JSON.parse(cached));
          }
        } catch {
          // ignore
        }
      });
    });

    window.addEventListener("lk-locale-change", renderLocaleButtons);
    window.addEventListener("lk-locale-change", () => {
      try {
        const cached = localStorage.getItem("currentUserProfile");
        if (cached) {
          applyRoleDataToUi(JSON.parse(cached));
        }
      } catch {
        // ignore
      }
    });
    renderLocaleButtons();
  }

  async function fetchFirstOk(path, options = {}) {
    for (const baseUrl of apiBases) {
      try {
        const response = await fetch(baseUrl + path, {
          ...options,
          credentials: "include",
          headers: { ...(options.headers || {}) },
        });
        if (response.ok) {
          return response;
        }
      } catch (error) {
        // Try next API base.
      }
    }
    return null;
  }

  function applyNavBadgesPayload(data) {
    if (!data || data.success === false) {
      return;
    }
    updateMessagesBadge(Number(data.unread_count) || 0);
    updateDocumentsBadge(
      Number(data.document_request_count) || 0,
      Number(data.document_rejected_count) || 0
    );
    updateClientsBadge(Number(data.clients_with_pending) || 0);
  }

  async function loadNavBadges() {
    const response = await fetchFirstOk("/lk/nav-badges", { method: "GET" });
    if (!response) {
      return false;
    }
    const data = await response.json();
    applyNavBadgesPayload(data);
    return Boolean(data && data.success !== false);
  }

  async function loadCurrentUser() {
    const response = await fetchFirstOk("/user", { method: "GET" });
    if (!response) {
      return false;
    }
    const payload = await response.json().catch(() => ({}));
    if (payload && payload.success === false) {
      return false;
    }
    if (!payload || payload.id == null) {
      return false;
    }
    persistUserProfileAndRefreshUi(payload);
    return true;
  }

  let lkSessionReadyResolved = false;
  let lkSessionReadyPromise = null;

  function whenLkSessionReady() {
    if (lkSessionReadyResolved) {
      return Promise.resolve(true);
    }
    if (!lkSessionReadyPromise) {
      lkSessionReadyPromise = new Promise((resolve, reject) => {
        window.__resolveLkSessionReady = resolve;
        window.__rejectLkSessionReady = reject;
      });
    }
    return lkSessionReadyPromise;
  }
  window.whenLkSessionReady = whenLkSessionReady;

  // Export to global scope for use in chat.js / profile.js
  window.loadUnreadMessagesCount = loadNavBadges;
  window.syncProfileNameRequiredMarkers = syncProfileNameRequiredMarkers;
  window.persistUserProfileAndRefreshUi = persistUserProfileAndRefreshUi;
  window.getLkCurrentUser = function () {
    return window.__lkCurrentUser || null;
  };
  window.canAccessLkPageGate = canAccessPageGate;
  window.isLkAccessDeniedPayload =
    window.isLkAccessDeniedPayload ||
    function (data) {
      if (!data || typeof data !== "object") return false;
      const err = String(data.error || data.message_ru || "").toLowerCase();
      return err.includes("access denied") || err.includes("нет доступа") || err.includes("недостаточно прав");
    };
  window.shouldRedirectLkAccessDenied =
    window.shouldRedirectLkAccessDenied ||
    function (response, data) {
      return (response && response.status === 403) || window.isLkAccessDeniedPayload(data);
    };

  function ensureUnifiedBadgeAnimationStyles() {
    if (document.getElementById("unified-badge-animation-style")) {
      return;
    }
    const style = document.createElement("style");
    style.id = "unified-badge-animation-style";
    style.textContent = `
      @keyframes badgePulse {
        0% { opacity: 0; transform: scale(1); }
        50% { opacity: 0.3; transform: scale(1.3); }
        100% { opacity: 0; transform: scale(1.5); }
      }
    `;
    document.head.appendChild(style);
  }

  function createAnimatedBadge(className, count, colorHex, rightPx, textOverride) {
    const label =
      textOverride != null && String(textOverride).length > 0
        ? String(textOverride)
        : count > 99
          ? "99+"
          : String(count);
    const badge = document.createElement("span");
    badge.className = className;
    badge.innerHTML = `
      <span class="badge-ripple"></span>
      <span class="badge-count">${label}</span>
    `;
    badge.style.cssText = `
      position: absolute;
      top: 8px;
      right: ${rightPx}px;
      background: ${colorHex};
      color: white;
      font-size: 10px;
      font-weight: bold;
      width: 20px;
      height: 20px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      overflow: visible;
    `;

    const ripple = badge.querySelector(".badge-ripple");
    if (ripple) {
      ripple.style.cssText = `
        position: absolute;
        inset: 0;
        border-radius: 50%;
        background: ${colorHex};
        z-index: -1;
        animation: badgePulse 1500ms cubic-bezier(0.9, 0.7, 0.5, 0.9) infinite;
      `;
    }

    const text = badge.querySelector(".badge-count");
    if (text) {
      text.style.cssText =
        textOverride != null && String(textOverride).length > 0
          ? "position: relative; z-index: 1; font-size: 11px; font-weight: 800; line-height: 1;"
          : "position: relative; z-index: 1;";
    }
    return badge;
  }

  function syncProfileNameRequiredMarkers(rawName) {
    const needs = !String(rawName ?? "").trim();
    ensureUnifiedBadgeAnimationStyles();

    const pairs = [
      ["profile-name-field-wrap", "profile-name-field-marker"],
      ["profile-name-field-wrap-desktop", "profile-name-field-marker-desktop"],
    ];
    pairs.forEach(([wrapId, markerId]) => {
      const wrap = document.getElementById(wrapId);
      const marker = document.getElementById(markerId);
      if (wrap) {
        wrap.classList.toggle("border-red-500", needs);
        wrap.classList.toggle("bg-red-50/30", needs);
        wrap.classList.toggle("border-transparent", !needs);
      }
      if (marker) {
        if (needs) {
          ensureRedPulseStyles();
        }
        marker.classList.toggle("hidden", !needs);
        marker.classList.toggle("pulser-red", needs);
      }
    });

    const profileLinks = Array.from(document.querySelectorAll('a[href*="profile.html"]')).filter((link) => {
      if (isBackNavigationLink(link)) {
        return false;
      }
      const icon = link.querySelector(".material-symbols-outlined");
      const iconText = icon ? String(icon.textContent || "").trim() : "";
      const text = String(link.textContent || "");
      return iconText === "tune" || text.includes("Настройки") || text.includes("Settings");
    });
    profileLinks.forEach((link) => {
      const existing = link.querySelector(".profile-name-required-badge");
      if (existing) {
        existing.remove();
      }
      if (!needs) {
        return;
      }
      if (getComputedStyle(link).position === "static") {
        link.style.position = "relative";
      }
      link.appendChild(createAnimatedBadge("profile-name-required-badge", 0, "#ef4444", 8, "!"));
    });
  }

  function isBackNavigationLink(link) {
    if (!link) {
      return false;
    }
    if (link.id === "back-btn") {
      return true;
    }
    const icon = link.querySelector(".material-symbols-outlined");
    const iconText = icon ? String(icon.textContent || "").trim().toLowerCase() : "";
    if (iconText === "arrow_back") {
      return true;
    }
    const text = String(link.textContent || "").toLowerCase();
    return text.includes("назад");
  }

  function updateMessagesBadge(count) {
    ensureUnifiedBadgeAnimationStyles();
    // Find all messages links (desktop and mobile)
    const messagesLinks = Array.from(document.querySelectorAll('a[href*="messages.html"]'))
      .filter((link) => !isBackNavigationLink(link));
    
    messagesLinks.forEach(link => {
      // Remove existing badge if any
      const existingBadge = link.querySelector('.unread-badge');
      if (existingBadge) {
        existingBadge.remove();
      }

      // Add badge if count > 0
      if (count > 0) {
        const badge = createAnimatedBadge("unread-badge", count, "#003ec7", 8);
        
        // Make link position relative if not already
        if (getComputedStyle(link).position === 'static') {
          link.style.position = 'relative';
        }
        
        link.appendChild(badge);
      }
    });
  }

  function ensureOrangePulseStyles() {
    if (document.getElementById("orange-pulser-style")) {
      return;
    }
    const style = document.createElement("style");
    style.id = "orange-pulser-style";
    style.textContent = `
      .pulser-orange { position: relative; }
      .pulser-orange::after {
        content: '';
        position: absolute;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
        background: #f97316;
        border-radius: 50%;
        z-index: -1;
        animation: pulse 1500ms cubic-bezier(0.9, 0.7, 0.5, 0.9) infinite;
      }
    `;
    document.head.appendChild(style);
  }

  function ensureRedPulseStyles() {
    if (document.getElementById("red-pulser-style")) {
      return;
    }
    const style = document.createElement("style");
    style.id = "red-pulser-style";
    style.textContent = `
      .pulser-red { position: relative; }
      .pulser-red::after {
        content: '';
        position: absolute;
        width: 100%;
        height: 100%;
        top: 0;
        left: 0;
        background: #ef4444;
        border-radius: 50%;
        z-index: -1;
        animation: pulse 1500ms cubic-bezier(0.9, 0.7, 0.5, 0.9) infinite;
      }
    `;
    document.head.appendChild(style);
  }

  function updateDocumentsBadge(requestCount, rejectedCount = 0) {
    ensureUnifiedBadgeAnimationStyles();
    const documentsLinks = Array.from(document.querySelectorAll('a[href*="documents.html"]'))
      .filter((link) => !isBackNavigationLink(link));

    documentsLinks.forEach((link) => {
      const existingRequestBadge = link.querySelector(".document-request-badge");
      if (existingRequestBadge) {
        existingRequestBadge.remove();
      }
      const existingRejectedBadge = link.querySelector(".document-rejected-badge");
      if (existingRejectedBadge) {
        existingRejectedBadge.remove();
      }

      if (getComputedStyle(link).position === "static") {
        link.style.position = "relative";
      }

      if (requestCount > 0) {
        const requestBadge = createAnimatedBadge("document-request-badge", requestCount, "#f97316", 8);
        link.appendChild(requestBadge);
      }

      if (rejectedCount > 0) {
        const rejectedBadge = createAnimatedBadge(
          "document-rejected-badge",
          rejectedCount,
          "#ef4444",
          requestCount > 0 ? 32 : 8
        );
        link.appendChild(rejectedBadge);
      }
    });
  }

  function updateClientsBadge(count) {
    ensureUnifiedBadgeAnimationStyles();
    const clientsLinks = Array.from(document.querySelectorAll('a[href*="clients.html"]'))
      .filter((link) => !isBackNavigationLink(link));

    clientsLinks.forEach((link) => {
      const existingBadge = link.querySelector(".clients-pending-badge");
      if (existingBadge) {
        existingBadge.remove();
      }

      if (count > 0) {
        const badge = createAnimatedBadge("clients-pending-badge", count, "#003ec7", 8);
        if (getComputedStyle(link).position === "static") {
          link.style.position = "relative";
        }
        link.appendChild(badge);
      }
    });
  }

  /** Синхронно подставить последний профиль из localStorage до ответа API (без «мигания» меню и шапки). */
  (function applyCachedUserProfileForInstantUi() {
    try {
      const raw = localStorage.getItem("currentUserProfile");
      if (!raw) {
        return;
      }
      const payload = JSON.parse(raw);
      if (!payload || typeof payload !== "object") {
        return;
      }
      if (payload.id == null && !payload.email) {
        return;
      }
      applyUserDataToUi(payload);
    } catch {
      // ignore invalid cache
    }
  })();

  async function bootstrapLkSession(retriesLeft = 3) {
    const userOk = await loadCurrentUser();
    if (!userOk) {
      if (retriesLeft > 0) {
        await new Promise((resolve) => window.setTimeout(resolve, 350));
        return bootstrapLkSession(retriesLeft - 1);
      }
      window.__rejectLkSessionReady?.(new Error("session expired"));
      clearLocalSession();
      window.location.href = loginUrl;
      return;
    }

    lkSessionReadyResolved = true;
    window.__resolveLkSessionReady?.(true);

    void loadNavBadges();
    if (!window.__lkNavBadgesInterval) {
      window.__lkNavBadgesInterval = window.setInterval(loadNavBadges, 30000);
    }
  }

  void bootstrapLkSession();

  // Initialize locale switcher
  initLocaleSwitcher();
})();
